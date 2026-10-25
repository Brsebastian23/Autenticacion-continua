package com.autentication.dto;

import jakarta.validation.constraints.NotEmpty;

import java.util.Map;

/**
 * DTO de entrada para verificar una muestra de tecleo (Opción 1).
 *
 * <p>El cliente (front/web o cualquier consumidor) envía las 31 features ya
 * calculadas de una repetición de la contraseña. El mapeo de claves debe
 * coincidir con las columnas del modelo Python: H.*, DD.* y UD.*.</p>
 *
 * @param features diccionario de 31 características (p. ej. {"H.period": 0.19, ...}).
 */
public record KeystrokeVerifyRequest(
        @NotEmpty(message = "El campo 'features' es obligatorio y no puede estar vacío")
        Map<String, Double> features
) {
}
