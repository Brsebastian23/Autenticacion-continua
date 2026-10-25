package com.autentication.client;

import java.util.List;
import java.util.Map;

/**
 * Abstracción del cliente hacia el servicio del modelo Python.
 *
 * <p>Capa de infraestructura. Al depender de esta interfaz (no de REST/WebClient
 * concretos) cumplimos el Principio de Inversión de Dependencias: los servicios
 * de dominio no conocen los detalles de transporte.</p>
 */
public interface KeystrokeModelClient {

    /**
     * Envía una muestra de tecleo al modelo y obtiene el resultado de inferencia.
     *
     * @param keystrokeModelId identificador del modelo ({@code user_id} en Python).
     * @param features         31 características precalculadas.
     * @return resultado normalizado de la inferencia.
     */
    ModelPrediction predict(String keystrokeModelId, Map<String, Double> features);

    /**
     * Reentrena el modelo del usuario con un conjunto de muestras ({@code /api/retrain/}).
     *
     * @param keystrokeModelId identificador del modelo ({@code user_id} en Python).
     * @param samples          lista de muestras (cada una con las 31 features).
     * @return resultado normalizado del entrenamiento.
     */
    TrainingResult retrain(String keystrokeModelId, List<Map<String, Double>> samples);

    /**
     * Resultado de inferencia devuelto por el modelo.
     *
     * @param legitimate      si la muestra corresponde al usuario legítimo.
     * @param confidenceScore score crudo de decision_function.
     * @param statusCode      LEGITIMATE | ANOMALY | ERROR.
     * @param latencyMs       latencia de inferencia (ms), puede ser null.
     */
    record ModelPrediction(
            boolean legitimate,
            double confidenceScore,
            String statusCode,
            Double latencyMs
    ) {
    }

    /**
     * Resultado del entrenamiento devuelto por el modelo.
     *
     * @param keystrokeModelId identificador del modelo entrenado.
     * @param samples          número de muestras usadas.
     * @param modelFile        nombre del archivo de modelo persistido.
     * @param latencyMs        latencia de entrenamiento (ms), puede ser null.
     */
    record TrainingResult(
            String keystrokeModelId,
            int samples,
            String modelFile,
            Double latencyMs
    ) {
    }
}
