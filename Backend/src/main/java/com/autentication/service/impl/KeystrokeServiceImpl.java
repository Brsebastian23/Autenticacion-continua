package com.autentication.service.impl;

import com.autentication.client.KeystrokeModelClient;
import com.autentication.client.KeystrokeModelClient.ModelPrediction;
import com.autentication.domain.User;
import com.autentication.dto.KeystrokeVerifyRequest;
import com.autentication.dto.KeystrokeVerifyResponse;
import com.autentication.exception.BadRequestException;
import com.autentication.exception.ResourceNotFoundException;
import com.autentication.repository.UserRepository;
import com.autentication.service.KeystrokeService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Set;

@Service
@RequiredArgsConstructor
@Slf4j
public class KeystrokeServiceImpl implements KeystrokeService {

    private static final Set<String> EXPECTED_FEATURE_KEYS = Set.of(
            "H.period", "H.t", "H.i", "H.e", "H.five", "H.Shift.r", "H.o", "H.a", "H.n", "H.l", "H.Return",
            "DD.period.t", "DD.t.i", "DD.i.e", "DD.e.five", "DD.five.Shift.r",
            "DD.Shift.r.o", "DD.o.a", "DD.a.n", "DD.n.l", "DD.l.Return",
            "UD.period.t", "UD.t.i", "UD.i.e", "UD.e.five", "UD.five.Shift.r",
            "UD.Shift.r.o", "UD.o.a", "UD.a.n", "UD.n.l", "UD.l.Return"
    );

    private final UserRepository userRepository;
    private final KeystrokeModelClient modelClient;

    @Override
    public KeystrokeVerifyResponse verify(String username, KeystrokeVerifyRequest request) {
        User user = userRepository.findByUsername(username)
                .orElseThrow(() -> new ResourceNotFoundException("Usuario no encontrado: " + username));

        Map<String, Double> features = request.features();
        validateFeatures(features);

        // Opción 2: usar el modelo propio si el usuario ya entrenó; si no, el del dataset.
        String activeModelId = user.activeModelId();
        ModelPrediction prediction = modelClient.predict(activeModelId, features);

        log.debug("Verificación de tecleo user={} model={} (propio={}) legit={} score={}",
                username, activeModelId, user.hasTrainedModel(),
                prediction.legitimate(), prediction.confidenceScore());

        return new KeystrokeVerifyResponse(
                user.getUsername(),
                activeModelId,
                prediction.legitimate(),
                prediction.confidenceScore(),
                prediction.statusCode(),
                prediction.latencyMs());
    }

    /**
     * Valida que las features tengan las 31 claves esperadas.
     * Falla temprano con un mensaje claro en lugar de en el modelo Python.
     */
    private void validateFeatures(Map<String, Double> features) {
        if (features.size() != EXPECTED_FEATURE_KEYS.size()) {
            throw new BadRequestException(
                    "Se esperaban %d features de tecleo, se recibieron %d."
                            .formatted(EXPECTED_FEATURE_KEYS.size(), features.size()));
        }
        Set<String> missing = EXPECTED_FEATURE_KEYS.stream()
                .filter(k -> !features.containsKey(k))
                .collect(java.util.stream.Collectors.toSet());
        if (!missing.isEmpty()) {
            throw new BadRequestException("Faltan features requeridas: " + missing);
        }
    }
}
