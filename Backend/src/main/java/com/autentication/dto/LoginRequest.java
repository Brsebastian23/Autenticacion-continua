package com.autentication.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * DTO de entrada para el login.
 */
public record LoginRequest(
        @NotBlank(message = "El username es obligatorio")
        String username,

        @NotBlank(message = "El password es obligatorio")
        String password
) {
}
