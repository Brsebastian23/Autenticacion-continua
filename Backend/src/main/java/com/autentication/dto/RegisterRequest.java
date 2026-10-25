package com.autentication.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * DTO de entrada para el registro de un nuevo usuario.
 *
 * @param username         nombre de usuario único.
 * @param password         contraseña en claro (se hashea antes de persistir).
 * @param keystrokeModelId identificador del modelo de tecleo asociado (p. ej. "s002").
 */
public record RegisterRequest(
        @NotBlank(message = "El username es obligatorio")
        @Size(min = 3, max = 64, message = "El username debe tener entre 3 y 64 caracteres")
        String username,

        @NotBlank(message = "El password es obligatorio")
        @Size(min = 6, max = 128, message = "El password debe tener entre 6 y 128 caracteres")
        String password,

        @NotBlank(message = "El keystrokeModelId es obligatorio")
        @Size(min = 1, max = 64, message = "El keystrokeModelId debe tener entre 1 y 64 caracteres")
        String keystrokeModelId
) {
}
