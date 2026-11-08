package com.autentication.controller;

import com.autentication.client.KeystrokeModelClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Verifica que el backend expone /api/metrics/* reenviando al modelo ML
 * (que se mockea aquí para no depender del microservicio Python).
 */
@SpringBootTest
@AutoConfigureMockMvc
class MetricsControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private KeystrokeModelClient modelClient;

    @Test
    void summaryEsAccesibleSinAutenticacionYDevuelveDatos() throws Exception {
        when(modelClient.metricsSummary()).thenReturn(Map.of(
                "n_subjects", 51,
                "aggregate", Map.of("eer", Map.of("mean", 0.1219))
        ));

        mockMvc.perform(get("/api/metrics/summary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.n_subjects").value(51))
                .andExpect(jsonPath("$.aggregate.eer.mean").value(0.1219));
    }

    @Test
    void curveEsAccesibleSinAutenticacion() throws Exception {
        when(modelClient.metricsCurve()).thenReturn(Map.of(
                "optimal_threshold", 0.021328,
                "points", List.of(Map.of("threshold", 0.0))
        ));

        mockMvc.perform(get("/api/metrics/curve"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.optimal_threshold").value(0.021328));
    }
}
