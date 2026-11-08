package com.autentication.controller;

import com.autentication.client.KeystrokeModelClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Verifica que el backend expone /api/cursor/* reenviando al modelo ML
 * (mockeado), sin requerir autenticación.
 */
@SpringBootTest
@AutoConfigureMockMvc
class CursorControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private KeystrokeModelClient modelClient;

    @Test
    void retrainEsAccesibleYReenviaAlModelo() throws Exception {
        when(modelClient.cursorRetrain(any())).thenReturn(Map.of(
                "status", "trained",
                "kind", "cursor",
                "samples", 40
        ));

        mockMvc.perform(post("/api/cursor/retrain")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"user_id\":\"s002\",\"synthetic\":true,\"n\":40}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.kind").value("cursor"))
                .andExpect(jsonPath("$.samples").value(40));
    }

    @Test
    void predictEsAccesibleYReenviaAlModelo() throws Exception {
        when(modelClient.cursorPredict(any())).thenReturn(Map.of(
                "is_legitimate", true,
                "confidence_score", 0.06,
                "threshold", 0.0
        ));

        mockMvc.perform(post("/api/cursor/predict")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"user_id\":\"s002\",\"record\":{\"M.speed_mean\":0.5}}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.is_legitimate").value(true))
                .andExpect(jsonPath("$.confidence_score").value(0.06));
    }
}
