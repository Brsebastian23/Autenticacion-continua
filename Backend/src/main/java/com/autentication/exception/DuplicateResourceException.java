package com.autentication.exception;

/**
 * Intento de crear un recurso que ya existe (username duplicado, etc.).
 */
public class DuplicateResourceException extends RuntimeException {
    public DuplicateResourceException(String message) {
        super(message);
    }
}
