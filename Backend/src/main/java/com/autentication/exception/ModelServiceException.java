package com.autentication.exception;

/**
 * Error al comunicarse con el servicio del modelo (Python) o respuesta inválida.
 */
public class ModelServiceException extends RuntimeException {
    public ModelServiceException(String message) {
        super(message);
    }

    public ModelServiceException(String message, Throwable cause) {
        super(message, cause);
    }
}
