package com.autentication.service;

import com.autentication.dto.KeystrokeVerifyRequest;
import com.autentication.dto.KeystrokeVerifyResponse;

/**
 * Contrato del servicio de verificación de tecleo.
 *
 * <p>Opción 1: recibe las features ya calculadas y las delega al modelo.
 * En el futuro (Opción 2) puede añadirse {@code verifyFromRawEvents(...)} sin
 * romper este contrato (Interface Segregation / Open-Closed).</p>
 */
public interface KeystrokeService {

    /**
     * Verifica una muestra de tecleo para el usuario autenticado.
     *
     * @param username usuario autenticado (del contexto de seguridad).
     * @param request  features precalculadas.
     * @return resultado de la verificación.
     */
    KeystrokeVerifyResponse verify(String username, KeystrokeVerifyRequest request);
}
