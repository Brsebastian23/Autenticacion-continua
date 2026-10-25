package com.autentication.dto;

import com.autentication.domain.User;

import java.time.Instant;

/**
 * DTO de salida con datos públicos de un usuario (sin contraseña).
 */
public record UserResponse(
        Long id,
        String username,
        String keystrokeModelId,
        String trainedModelId,
        boolean trained,
        String activeModelId,
        Instant createdAt
) {
    public static UserResponse from(User user) {
        return new UserResponse(
                user.getId(),
                user.getUsername(),
                user.getKeystrokeModelId(),
                user.getTrainedModelId(),
                user.hasTrainedModel(),
                user.activeModelId(),
                user.getCreatedAt());
    }
}
