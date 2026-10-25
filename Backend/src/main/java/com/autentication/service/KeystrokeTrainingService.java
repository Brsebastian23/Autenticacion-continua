package com.autentication.service;

import com.autentication.dto.KeystrokeTrainRequest;
import com.autentication.dto.KeystrokeTrainResponse;

/**
 * Contrato del servicio de entrenamiento de modelos de tecleo.
 *
 * <p>Responsabilidad separada de la verificación (Single Responsibility):
 * entrenar y verificar son casos de uso distintos.</p>
 */
public interface KeystrokeTrainingService {

    /**
     * Entrena/reentrena el modelo del usuario autenticado con las muestras dadas.
     *
     * @param username usuario autenticado (del contexto de seguridad).
     * @param request  muestras de tecleo (cada una con las 31 features).
     * @return resultado del entrenamiento.
     */
    KeystrokeTrainResponse train(String username, KeystrokeTrainRequest request);
}
