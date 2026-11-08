"""Pruebas del microservicio ML.

Cubre:
- Conversión de registros a vectores (``record_to_vector``).
- Construcción de matrices y validaciones (``build_matrix``).
- Entrenamiento e inferencia del IsolationForest.
- Métricas de evaluación (FAR/FRR/EER/AUC) incluyendo ``metrics.py``.
- Endpoints de métricas (``/api/metrics/summary/`` y ``/api/metrics/curve/``).

Ejecutar con:
    python manage.py test authentication_api
"""

import json
import tempfile
from pathlib import Path

import numpy as np
from django.test import TestCase, override_settings

from authentication_api import metrics as M
from authentication_api.ml_service import (
    FEATURE_COLUMNS,
    MLServiceError,
    build_matrix,
    predict,
    record_to_vector,
    train_model,
)
from authentication_api import cursor_service as CS
from authentication_api import ml_service as MS


def _sample(offset: float = 0.0):
    """Muestra sintética con las 31 features."""
    return {col: 0.1 + offset + i * 0.001 for i, col in enumerate(FEATURE_COLUMNS)}


class RecordToVectorTests(TestCase):
    def test_dict_valido_devuelve_vector_1x31(self):
        vector = record_to_vector(_sample())
        self.assertEqual(vector.shape, (1, len(FEATURE_COLUMNS)))

    def test_dict_incompleto_lanza_error(self):
        rec = _sample()
        del rec[FEATURE_COLUMNS[0]]
        with self.assertRaises(MLServiceError):
            record_to_vector(rec)

    def test_lista_tamano_incorrecto_lanza_error(self):
        with self.assertRaises(MLServiceError):
            record_to_vector([0.1, 0.2, 0.3])

    def test_valor_no_numerico_lanza_error(self):
        rec = _sample()
        rec[FEATURE_COLUMNS[0]] = "no-numero"
        with self.assertRaises(MLServiceError):
            record_to_vector(rec)

    def test_nan_lanza_error(self):
        rec = _sample()
        rec[FEATURE_COLUMNS[0]] = float('nan')
        with self.assertRaises(MLServiceError):
            record_to_vector(rec)


class BuildMatrixTests(TestCase):
    def test_menos_de_tres_muestras_falla(self):
        with self.assertRaises(MLServiceError):
            build_matrix([_sample(), _sample(0.01)])

    def test_no_lista_falla(self):
        with self.assertRaises(MLServiceError):
            build_matrix("no-soy-lista")

    def test_matriz_valida(self):
        matrix = build_matrix([_sample(i * 0.001) for i in range(5)])
        self.assertEqual(matrix.shape, (5, len(FEATURE_COLUMNS)))


class TrainPredictTests(TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix='ml_test_'))

    def test_entrena_y_predice(self):
        with override_settings(ML_MODELS_DIR=self._tmp):
            rng = np.random.default_rng(0)
            base = np.array([_sample()[c] for c in FEATURE_COLUMNS])
            records = [
                {c: float(base[i] + rng.normal(0, 0.001)) for i, c in enumerate(FEATURE_COLUMNS)}
                for _ in range(30)
            ]
            result = train_model('test-user', records)
            self.assertEqual(result['samples'], 30)
            near = {c: float(base[i] + 0.0005) for i, c in enumerate(FEATURE_COLUMNS)}
            pred = predict('test-user', near)
            self.assertIn('confidence_score', pred)
            self.assertIn('is_legitimate', pred)

    def test_predict_usuario_sin_modelo_falla(self):
        with override_settings(ML_MODELS_DIR=self._tmp):
            with self.assertRaises(MLServiceError):
                predict('no-existe', _sample())


class MetricsTests(TestCase):
    """Verifica el cálculo de FAR/FRR/EER/AUC con casos de verdad conocida."""

    def test_far_frr_at(self):
        genuine = np.array([0.5, 0.6, 0.7])
        impostor = np.array([-0.5, -0.6])
        far, frr = M.far_frr_at(genuine, impostor, threshold=0.0)
        self.assertEqual(far, 0.0)
        self.assertEqual(frr, 0.0)

    def test_eer_separacion_total(self):
        genuine = np.array([1.0, 1.1, 1.2])
        impostor = np.array([-1.0, -1.1])
        res = M.eer(genuine, impostor)
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res['eer'], 0.0, places=6)

    def test_eer_solapamiento(self):
        # Distribuciones solapadas: EER > 0 y el umbral elegido minimiza |FAR-FRR|.
        genuine = np.array([0.1, 0.2, 0.3, 0.4])
        impostor = np.array([0.0, 0.1, 0.2, 0.3])
        res = M.eer(genuine, impostor)
        self.assertGreater(res['eer'], 0.0)
        # El gap entre FAR y FRR en el punto elegido debe ser el mínimo posible.
        self.assertLessEqual(abs(res['far_at_eer'] - res['frr_at_eer']), 0.25 + 1e-9)

    def test_eer_sin_datos_es_none(self):
        self.assertIsNone(M.eer(np.array([]), np.array([1.0])))

    def test_auc_separacion_perfecta(self):
        genuine = np.array([1.0, 2.0, 3.0])
        impostor = np.array([-1.0, -2.0])
        self.assertAlmostEqual(M.auc_roc(genuine, impostor), 1.0, places=6)

    def test_auc_mayormente_separado(self):
        # 3 de 4 genuinos por encima de todos los impostores => AUC = 0.75.
        genuine = np.array([5.0, 6.0, 7.0, -3.0])
        impostor = np.array([0.0, 1.0, 2.0, 3.0])
        self.assertAlmostEqual(M.auc_roc(genuine, impostor), 0.75, places=6)

    def test_summarize_benchmark(self):
        summary = M.summarize_benchmark([0.1, 0.2, None, 0.3])
        self.assertEqual(summary['count'], 3)
        self.assertAlmostEqual(summary['mean'], 0.2, places=6)
        self.assertAlmostEqual(summary['median'], 0.2, places=6)


class MetricsEndpointsTests(TestCase):
    """Prueba los endpoints de métricas sirviendo un benchmark temporal."""

    def setUp(self):
        self._dir = Path(tempfile.mkdtemp(prefix='bench_'))
        self._json = self._dir / 'benchmark_eer.json'
        self._payload = {
            'dataset': 'DSL-StrongPasswordData.csv',
            'generated_at': '2026-01-01T00:00:00+00:00',
            'n_subjects': 2,
            'train_sessions': '1-6',
            'reference_threshold': 0.0,
            'optimal_threshold': 0.02,
            'aggregate': {
                'eer': {'mean': 0.12, 'median': 0.11, 'min': 0.01,
                        'max': 0.10, 'std': 0.03, 'count': 2},
                'auc': {'mean': 0.94, 'count': 2},
                'far_at_reference': 0.27,
                'frr_at_reference': 0.06,
                'accuracy_at_reference': 0.73,
            },
            'per_subject': [{'subject': 's002', 'threshold_at_eer': 0.02}],
        }
        self._json.write_text(json.dumps(self._payload), encoding='utf-8')

    def test_summary_y_curve(self):
        import authentication_api.views as views
        original = views.BENCHMARK_JSON
        views.BENCHMARK_JSON = self._json
        try:
            r = self.client.get('/api/metrics/summary/')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['n_subjects'], 2)
            self.assertAlmostEqual(r.json()['aggregate']['eer']['mean'], 0.12)

            r2 = self.client.get('/api/metrics/curve/')
            self.assertEqual(r2.status_code, 200)
            self.assertIn('points', r2.json())
        finally:
            views.BENCHMARK_JSON = original

    def test_sin_benchmark_devuelve_404(self):
        import authentication_api.views as views
        original = views.BENCHMARK_JSON
        views.BENCHMARK_JSON = self._dir / 'no-existe.json'
        try:
            r = self.client.get('/api/metrics/summary/')
            self.assertEqual(r.status_code, 404)
        finally:
            views.BENCHMARK_JSON = original


class ModelStorageSeparationTests(TestCase):
    """Separación dataset (imagen) vs usuario (volumen persistente)."""

    def setUp(self):
        self._data_dir = Path(tempfile.mkdtemp(prefix='dataset_'))
        self._user_dir = Path(tempfile.mkdtemp(prefix='user_models_'))

    def test_is_user_model(self):
        self.assertTrue(MS.is_user_model('user-alice'))
        self.assertFalse(MS.is_user_model('s002'))

    def test_modelo_dataset_va_a_models_dir(self):
        with override_settings(ML_MODELS_DIR=self._data_dir,
                               ML_USER_MODELS_DIR=self._user_dir):
            path = MS.model_path_for('s002')
            self.assertEqual(path.parent, self._data_dir)

    def test_modelo_usuario_va_a_user_models_dir(self):
        with override_settings(ML_MODELS_DIR=self._data_dir,
                               ML_USER_MODELS_DIR=self._user_dir):
            path = MS.model_path_for('user-alice')
            self.assertEqual(path.parent, self._user_dir)

    def test_sin_user_models_dir_cae_a_models_dir(self):
        # Compatibilidad: si el setting no está, todo cae a ML_MODELS_DIR.
        with override_settings(ML_MODELS_DIR=self._data_dir):
            from django.conf import settings as dj_settings
            had = hasattr(dj_settings, 'ML_USER_MODELS_DIR')
            original = getattr(dj_settings, 'ML_USER_MODELS_DIR', None)
            try:
                if had:
                    del dj_settings.ML_USER_MODELS_DIR
                path = MS.model_path_for('user-bob')
                self.assertEqual(path.parent, self._data_dir)
            finally:
                if had:
                    dj_settings.ML_USER_MODELS_DIR = original

    def test_cursor_modelo_va_a_user_models_dir(self):
        with override_settings(ML_MODELS_DIR=self._data_dir,
                               ML_USER_MODELS_DIR=self._user_dir):
            path = CS.cursor_model_path_for('alice')
            self.assertEqual(path.parent, self._user_dir)

    def test_entrenar_usuario_persiste_en_volumen(self):
        # End-to-end: entrenar un modelo de usuario lo deja en el volumen,
        # y el modelo de dataset no se toca.
        with override_settings(ML_MODELS_DIR=self._data_dir,
                               ML_USER_MODELS_DIR=self._user_dir):
            records = CS.generate_synthetic_cursor_records('alice', n=10)
            # Cursor siempre es de usuario -> volumen.
            CS.train_cursor_model('alice', records)
            self.assertTrue((self._user_dir / 'cursor_iforest_alice.joblib').exists())
            self.assertFalse((self._data_dir / 'cursor_iforest_alice.joblib').exists())


class CursorSyntheticTests(TestCase):
    """Generador sintético de cursor: forma, reproducibilidad y coherencia."""

    def test_genera_n_muestras_con_todas_las_features(self):
        records = CS.generate_synthetic_cursor_records('s002', n=10)
        self.assertEqual(len(records), 10)
        for rec in records:
            self.assertEqual(set(rec), set(CS.CURSOR_FEATURE_COLUMNS))

    def test_reproducible_para_mismo_usuario_y_semilla(self):
        a = CS.generate_synthetic_cursor_records('s002', n=5, seed=1)
        b = CS.generate_synthetic_cursor_records('s002', n=5, seed=1)
        self.assertEqual(a, b)

    def test_perfil_estable_por_usuario(self):
        # El perfil asignado no cambia entre llamadas.
        self.assertEqual(CS.synthetic_profile_for('s047'),
                         CS.synthetic_profile_for('s047'))

    def test_cotas_fisicas(self):
        for rec in CS.generate_synthetic_cursor_records('s010', n=20):
            self.assertGreaterEqual(rec['M.speed_mean'], 0.0)
            self.assertGreaterEqual(rec['M.pause_count'], 0.0)
            self.assertLessEqual(rec['M.pause_ratio'], 1.0)
            self.assertGreaterEqual(rec['M.straightness'], 0.0)
            self.assertLessEqual(rec['M.straightness'], 1.0)


class CursorModelTests(TestCase):
    """Entrenamiento e inferencia del modelo de cursor (aislado en tmp)."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix='cursor_test_'))

    def test_entrena_y_separa_legitimo_de_impostor(self):
        with override_settings(ML_MODELS_DIR=self._tmp):
            legit_train = CS.generate_synthetic_cursor_records('s002', n=40, seed=7)
            CS.train_cursor_model('s002', legit_train)

            legit = CS.generate_synthetic_cursor_records('s002', n=1, seed=999)[0]
            res_legit = CS.predict_cursor('s002', legit)
            self.assertIn('confidence_score', res_legit)
            self.assertTrue(res_legit['is_legitimate'])

            # Un impostor de otro perfil debe puntuar más bajo.
            impostor = CS.generate_synthetic_cursor_records('s047', n=1, seed=123)[0]
            res_imp = CS.predict_cursor('s002', impostor)
            self.assertLess(res_imp['confidence_score'],
                            res_legit['confidence_score'])

    def test_predict_sin_modelo_falla(self):
        with override_settings(ML_MODELS_DIR=self._tmp):
            with self.assertRaises(CS.CursorServiceError):
                CS.predict_cursor('no-existe',
                                  CS.generate_synthetic_cursor_records('x', n=1)[0])

    def test_menos_de_tres_muestras_falla(self):
        with self.assertRaises(CS.CursorServiceError):
            CS.train_cursor_model('s002',
                                  CS.generate_synthetic_cursor_records('s002', n=2))


class CursorEndpointsTests(TestCase):
    """Endpoints HTTP de cursor."""

    def test_synthetic_dataset(self):
        r = self.client.get('/api/cursor/synthetic/?user_id=s002&n=5')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['n'], 5)
        self.assertEqual(len(body['features']), CS.NUM_CURSOR_FEATURES)
        self.assertEqual(len(body['records']), 5)

    def test_retrain_synthetic_y_predict(self):
        tmp = Path(tempfile.mkdtemp(prefix='cursor_ep_'))
        with override_settings(ML_MODELS_DIR=tmp):
            r = self.client.post(
                '/api/cursor/retrain/',
                data=json.dumps({'user_id': 's002', 'synthetic': True, 'n': 30}),
                content_type='application/json',
            )
            self.assertEqual(r.status_code, 201)
            self.assertEqual(r.json()['kind'], 'cursor')

            record = CS.generate_synthetic_cursor_records('s002', n=1, seed=5)[0]
            r2 = self.client.post(
                '/api/cursor/predict/',
                data=json.dumps({'user_id': 's002', 'record': record}),
                content_type='application/json',
            )
            self.assertEqual(r2.status_code, 200)
            self.assertIn('is_legitimate', r2.json())

    def test_predict_sin_record_400(self):
        r = self.client.post(
            '/api/cursor/predict/',
            data=json.dumps({'user_id': 's002'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)
