package com.autentication.controller;

import com.autentication.dto.KeystrokeVerifyRequest;
import com.autentication.dto.KeystrokeVerifyResponse;
import com.autentication.service.KeystrokeService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.web.bind.annotation.*;

/**
 * Endpoints de verificación biométrica de tecleo.
 * Requiere autenticación (JWT): el usuario evaluado es el autenticado.
 */
@RestController
@RequestMapping("/api/keystroke")
@RequiredArgsConstructor
public class KeystrokeController {

    private final KeystrokeService keystrokeService;

    /**
     * Verifica una repetición de la contraseña (features ya calculadas).
     * Opción 1: el cliente envía las 31 features y el backend las delega al modelo.
     */
    @PostMapping("/verify")
    public KeystrokeVerifyResponse verify(
            @AuthenticationPrincipal UserDetails userDetails,
            @Valid @RequestBody KeystrokeVerifyRequest request) {
        return keystrokeService.verify(userDetails.getUsername(), request);
    }
}
