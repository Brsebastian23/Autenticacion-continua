package com.autentication.controller;

import com.autentication.client.KeystrokeModelClient;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Expone las métricas de exactitud del modelo (EER, FAR, FRR, AUC) calculadas
 * por el microservicio ML. El backend actúa de fachada para que el frontend
 * hable un único origen (evita CORS y funciona en Render).
 *
 * <p>Son datos de referencia del benchmark (no por usuario concreto), por lo que
 * no requieren autenticación.</p>
 */
@RestController
@RequestMapping("/api/metrics")
@RequiredArgsConstructor
public class MetricsController {

    private final KeystrokeModelClient modelClient;

    /** GET /api/metrics/summary/ — EER agregado, AUC, FAR/FRR y umbral óptimo. */
    @GetMapping("/summary")
    public Map<String, Object> summary() {
        return modelClient.metricsSummary();
    }

    /** GET /api/metrics/curve/ — puntos de la curva FAR vs FRR. */
    @GetMapping("/curve")
    public Map<String, Object> curve() {
        return modelClient.metricsCurve();
    }
}
