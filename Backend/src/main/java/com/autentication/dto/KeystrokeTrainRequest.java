package com.autentication.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.Map;

/**
 * DTO de entrada para entrenar el modelo de tecleo del usuario autenticado.
 *
 * <p>El cliente envía N muestras (cada una con las 31 features) capturadas de
 * varias repeticiones de la contraseña. Con ellas se entrena/reentrena el
 * modelo del usuario en el servicio Python ({@code /api/retrain/}).</p>
 *
 * @param samples lista de muestras (cada una con las 31 features del tecleo).
 */
public record KeystrokeTrainRequest(
        @NotNull(message = "El campo 'samples' es obligatorio")
        @Size(min = 3, message = "Se requieren al menos 3 muestras para entrenar")
        List<Map<String, Double>> samples
) {
}
