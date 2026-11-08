package com.autentication.controller;

import com.autentication.client.KeystrokeModelClient;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Fachada hacia el modelo de **dinámica del cursor** (mouse dynamics) del
 * microservicio ML. Totalmente independiente del flujo de tecleo.
 *
 * <p>Público (como /api/metrics): los datos de cursor son de demo/prueba y el
 * user_id identifica el modelo en el microservicio, no un recurso protegido.</p>
 */
@RestController
@RequestMapping("/api/cursor")
@RequiredArgsConstructor
public class CursorController {

    private final KeystrokeModelClient modelClient;

    /**
     * POST /api/cursor/retrain/
     * Body: { "user_id": "...", "records": [...] } o { "user_id": "...", "synthetic": true, "n": 30 }
     */
    @PostMapping("/retrain")
    public Map<String, Object> retrain(@RequestBody Map<String, Object> payload) {
        return modelClient.cursorRetrain(payload);
    }

    /**
     * POST /api/cursor/predict/
     * Body: { "user_id": "...", "record": { ...12 features... } }
     */
    @PostMapping("/predict")
    public Map<String, Object> predict(@RequestBody Map<String, Object> payload) {
        return modelClient.cursorPredict(payload);
    }
}
