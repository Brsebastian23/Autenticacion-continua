package com.autentication.exception;

/**
 * Recurso no encontrado (usuario inexistente, etc.).
 */
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String message) {
        super(message);
    }
}
