package com.autentication.service;

import com.autentication.exception.BadRequestException;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Valida que un mapa de features contenga exactamente las 31 claves esperadas
 * por el modelo (H.*, DD.*, UD.*).
 */
@Component
public class KeystrokeFeatureValidator {

    public static final Set<String> EXPECTED_FEATURE_KEYS = Set.of(
            "H.period", "H.t", "H.i", "H.e", "H.five", "H.Shift.r", "H.o", "H.a", "H.n", "H.l", "H.Return",
            "DD.period.t", "DD.t.i", "DD.i.e", "DD.e.five", "DD.five.Shift.r",
            "DD.Shift.r.o", "DD.o.a", "DD.a.n", "DD.n.l", "DD.l.Return",
            "UD.period.t", "UD.t.i", "UD.i.e", "UD.e.five", "UD.five.Shift.r",
            "UD.Shift.r.o", "UD.o.a", "UD.a.n", "UD.n.l", "UD.l.Return"
    );

    public void validate(Map<String, Double> features) {
        if (features == null) {
            throw new BadRequestException("Las features son obligatorias.");
        }
        if (features.size() != EXPECTED_FEATURE_KEYS.size()) {
            throw new BadRequestException(
                    "Se esperaban %d features de tecleo, se recibieron %d."
                            .formatted(EXPECTED_FEATURE_KEYS.size(), features.size()));
        }
        Set<String> missing = EXPECTED_FEATURE_KEYS.stream()
                .filter(k -> !features.containsKey(k))
                .collect(Collectors.toSet());
        if (!missing.isEmpty()) {
            throw new BadRequestException("Faltan features requeridas: " + missing);
        }
    }
}
