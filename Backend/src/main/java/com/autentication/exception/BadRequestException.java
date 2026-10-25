package com.autentication.exception;

/**
 * Petición inválida (validaciones de negocio que no cubren las anotaciones).
 */
public class BadRequestException extends RuntimeException {
    public BadRequestException(String message) {
        super(message);
    }
}
