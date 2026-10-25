package com.autentication.dto;

/**
 * DTO de salida con el resultado del entrenamiento del modelo del usuario.
 *
 * @param username        usuario entrenado (identidad Java).
 * @param keystrokeModelId identificador del modelo entrenado.
 * @param samples         número de muestras usadas en el entrenamiento.
 * @param modelFile       nombre del archivo de modelo persistido.
 * @param latencyMs       latencia de entrenamiento (ms), puede ser null.
 */
public record KeystrokeTrainResponse(
        String username,
        String keystrokeModelId,
        int samples,
        String modelFile,
        Double latencyMs
) {
}
