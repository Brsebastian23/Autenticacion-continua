package com.autentication.dto;

/**
 * DTO de salida con el resultado de la verificación de tecleo.
 *
 * <p>Refleja la respuesta del modelo Python ({@code /api/predict/}).</p>
 *
 * @param username        usuario evaluado (identidad Java).
 * @param keystrokeModelId identificador del modelo usado.
 * @param legitimate      true si la muestra se considera del usuario legítimo.
 * @param confidenceScore score crudo de decision_function del IsolationForest.
 * @param statusCode      LEGITIMATE | ANOMALY | ERROR.
 * @param latencyMs       latencia de inferencia reportada por el modelo.
 */
public record KeystrokeVerifyResponse(
        String username,
        String keystrokeModelId,
        boolean legitimate,
        double confidenceScore,
        String statusCode,
        Double latencyMs
) {
}
