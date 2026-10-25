package com.autentication.controller;

import com.autentication.dto.KeystrokeTrainRequest;
import com.autentication.dto.KeystrokeTrainResponse;
import com.autentication.service.KeystrokeTrainingService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.web.bind.annotation.*;

/**
 * Endpoints de entrenamiento del modelo de tecleo.
 * Requiere autenticación (JWT): el modelo entrenado es el del usuario autenticado.
 */
@RestController
@RequestMapping("/api/keystroke")
@RequiredArgsConstructor
public class TrainingController {

    private final KeystrokeTrainingService trainingService;

    /**
     * Entrena/reentrena el modelo del usuario con N muestras (p. ej. 10 repeticiones).
     */
    @PostMapping("/train")
    public KeystrokeTrainResponse train(
            @AuthenticationPrincipal UserDetails userDetails,
            @Valid @RequestBody KeystrokeTrainRequest request) {
        return trainingService.train(userDetails.getUsername(), request);
    }
}
