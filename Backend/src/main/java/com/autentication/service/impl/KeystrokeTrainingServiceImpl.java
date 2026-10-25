package com.autentication.service.impl;

import com.autentication.client.KeystrokeModelClient;
import com.autentication.client.KeystrokeModelClient.TrainingResult;
import com.autentication.domain.User;
import com.autentication.dto.KeystrokeTrainRequest;
import com.autentication.dto.KeystrokeTrainResponse;
import com.autentication.exception.BadRequestException;
import com.autentication.exception.ResourceNotFoundException;
import com.autentication.repository.UserRepository;
import com.autentication.service.KeystrokeFeatureValidator;
import com.autentication.service.KeystrokeTrainingService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
@Slf4j
public class KeystrokeTrainingServiceImpl implements KeystrokeTrainingService {

    private final UserRepository userRepository;
    private final KeystrokeModelClient modelClient;
    private final KeystrokeFeatureValidator featureValidator;

    /** Prefijo del modelo propio del usuario, para no colisionar con los del dataset (sXXX). */
    private static final String USER_MODEL_PREFIX = "user-";

    @Override
    public KeystrokeTrainResponse train(String username, KeystrokeTrainRequest request) {
        User user = userRepository.findByUsername(username)
                .orElseThrow(() -> new ResourceNotFoundException("Usuario no encontrado: " + username));

        List<Map<String, Double>> samples = request.samples();
        // Validar cada muestra: debe tener las 31 claves esperadas.
        for (int i = 0; i < samples.size(); i++) {
            try {
                featureValidator.validate(samples.get(i));
            } catch (RuntimeException ex) {
                throw new BadRequestException(
                        "Muestra #%d inválida: %s".formatted(i + 1, ex.getMessage()));
            }
        }

        // Opción 2: el entrenamiento SIEMPRE va a un modelo propio del usuario,
        // NUNCA al modelo del dataset (keystrokeModelId), que es de solo lectura.
        String userModelId = USER_MODEL_PREFIX + user.getUsername();
        TrainingResult result = modelClient.retrain(userModelId, samples);

        // Persistir el modelo propio en el usuario para que la verificación lo use.
        user.setTrainedModelId(userModelId);
        userRepository.save(user);

        log.info("Modelo propio entrenado user={} model={} samples={} (dataset intacto={})",
                username, userModelId, result.samples(), user.getKeystrokeModelId());

        return new KeystrokeTrainResponse(
                user.getUsername(),
                userModelId,
                result.samples(),
                result.modelFile(),
                result.latencyMs());
    }
}
