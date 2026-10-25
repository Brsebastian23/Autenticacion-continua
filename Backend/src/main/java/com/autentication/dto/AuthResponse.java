package com.autentication.dto;

/**
 * DTO de salida tras un login/registro exitoso.
 *
 * @param token          JWT de acceso.
 * @param username       nombre del usuario autenticado.
 * @param keystrokeModelId identificador del modelo de tecleo del usuario.
 */
public record AuthResponse(
        String token,
        String username,
        String keystrokeModelId
) {
}
