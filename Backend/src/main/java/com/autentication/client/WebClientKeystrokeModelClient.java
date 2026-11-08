package com.autentication.client;

import com.autentication.exception.ModelServiceException;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Implementación basada en WebClient del cliente del modelo Python.
 *
 * <p>Traduce el modelo de dominio (features + keystrokeModelId) al contrato
 * del endpoint {@code /api/predict/} y normaliza la respuesta.</p>
 */
@Component
@Slf4j
public class WebClientKeystrokeModelClient implements KeystrokeModelClient {

    private final WebClient webClient;
    private final String predictPath;
    private final String retrainPath;
    private final String metricsSummaryPath;
    private final String metricsCurvePath;
    private final String cursorRetrainPath;
    private final String cursorPredictPath;
    private final long readTimeoutMs;

    public WebClientKeystrokeModelClient(
            WebClient.Builder webClientBuilder,
            @Value("${app.ml.base-url}") String baseUrl,
            @Value("${app.ml.predict-path}") String predictPath,
            @Value("${app.ml.retrain-path}") String retrainPath,
            @Value("${app.ml.metrics-summary-path:/api/metrics/summary/}") String metricsSummaryPath,
            @Value("${app.ml.metrics-curve-path:/api/metrics/curve/}") String metricsCurvePath,
            @Value("${app.ml.cursor-retrain-path:/api/cursor/retrain/}") String cursorRetrainPath,
            @Value("${app.ml.cursor-predict-path:/api/cursor/predict/}") String cursorPredictPath,
            @Value("${app.ml.read-timeout-ms}") long readTimeoutMs) {
        this.webClient = webClientBuilder.baseUrl(baseUrl).build();
        this.predictPath = predictPath;
        this.retrainPath = retrainPath;
        this.metricsSummaryPath = metricsSummaryPath;
        this.metricsCurvePath = metricsCurvePath;
        this.cursorRetrainPath = cursorRetrainPath;
        this.cursorPredictPath = cursorPredictPath;
        this.readTimeoutMs = readTimeoutMs;
    }

    @Override
    public ModelPrediction predict(String keystrokeModelId, Map<String, Double> features) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("user_id", keystrokeModelId);
        payload.put("record", features);

        ModelPredictResponse response;
        try {
            response = webClient.post()
                    .uri(predictPath)
                    .bodyValue(payload)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, resp -> resp.bodyToMono(String.class)
                            .defaultIfEmpty("")
                            .map(body -> new ModelServiceException(
                                    "El modelo respondió %s: %s".formatted(resp.statusCode(), body))))
                    .bodyToMono(ModelPredictResponse.class)
                    .timeout(Duration.ofMillis(readTimeoutMs))
                    .retryWhen(Retry.max(1)
                            .filter(ex -> ex instanceof ModelServiceException == false)
                            .doBeforeRetry(sig -> log.warn("Reintentando llamada al modelo: {}",
                                    sig.failure().getMessage())))
                    .onErrorMap(ex -> ex instanceof ModelServiceException
                            ? ex
                            : new ModelServiceException("No fue posible comunicarse con el modelo: "
                                    + ex.getMessage(), ex))
                    .block();
        } catch (ModelServiceException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ModelServiceException("Error inesperado llamando al modelo: "
                    + ex.getMessage(), ex);
        }

        if (response == null || response.confidenceScore() == null) {
            throw new ModelServiceException("Respuesta vacía o inválida del modelo.");
        }

        return new ModelPrediction(
                Boolean.TRUE.equals(response.isLegitimate()),
                response.confidenceScore(),
                response.statusCode() != null ? response.statusCode() : "UNKNOWN",
                response.latencyMs());
    }

    @Override
    public TrainingResult retrain(String keystrokeModelId, List<Map<String, Double>> samples) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("user_id", keystrokeModelId);
        payload.put("records", new ArrayList<>(samples));

        ModelRetrainResponse response;
        try {
            response = webClient.post()
                    .uri(retrainPath)
                    .bodyValue(payload)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, resp -> resp.bodyToMono(String.class)
                            .defaultIfEmpty("")
                            .map(body -> new ModelServiceException(
                                    "El modelo respondió %s: %s".formatted(resp.statusCode(), body))))
                    .bodyToMono(ModelRetrainResponse.class)
                    .timeout(Duration.ofMillis(readTimeoutMs))
                    .onErrorMap(ex -> ex instanceof ModelServiceException
                            ? ex
                            : new ModelServiceException("No fue posible entrenar con el modelo: "
                                    + ex.getMessage(), ex))
                    .block();
        } catch (ModelServiceException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ModelServiceException("Error inesperado entrenando con el modelo: "
                    + ex.getMessage(), ex);
        }

        if (response == null || response.samples() == null) {
            throw new ModelServiceException("Respuesta vacía o inválida del entrenamiento.");
        }

        return new TrainingResult(
                response.userId() != null ? response.userId() : keystrokeModelId,
                response.samples(),
                response.modelFile(),
                response.trainingLatencyMs());
    }

    /**
     * Mapeo del JSON devuelto por el modelo Python ({@code /api/retrain/}).
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    record ModelRetrainResponse(
            @JsonProperty("user_id") String userId,
            @JsonProperty("samples") Integer samples,
            @JsonProperty("model_file") String modelFile,
            @JsonProperty("training_latency_ms") Double trainingLatencyMs
    ) {
    }

    /**
     * Mapeo del JSON devuelto por el modelo Python ({@code /api/predict/}).
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    record ModelPredictResponse(
            @JsonProperty("is_legitimate") Boolean isLegitimate,
            @JsonProperty("confidence_score") Double confidenceScore,
            @JsonProperty("status_code") String statusCode,
            @JsonProperty("latency_ms") Double latencyMs
    ) {
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> metricsSummary() {
        return getJson(metricsSummaryPath, "métricas de resumen");
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> metricsCurve() {
        return getJson(metricsCurvePath, "curva FAR/FRR");
    }

    @Override
    public Map<String, Object> cursorRetrain(Map<String, Object> payload) {
        return postJson(cursorRetrainPath, payload, "entrenamiento de cursor");
    }

    @Override
    public Map<String, Object> cursorPredict(Map<String, Object> payload) {
        return postJson(cursorPredictPath, payload, "inferencia de cursor");
    }

    /**
     * POST genérico hacia el microservicio ML que devuelve un mapa JSON.
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> postJson(String path, Map<String, Object> payload,
                                         String description) {
        try {
            Map<String, Object> response = webClient.post()
                    .uri(path)
                    .bodyValue(payload)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, resp -> resp.bodyToMono(String.class)
                            .defaultIfEmpty("")
                            .map(body -> new ModelServiceException(
                                    "El modelo respondió %s: %s".formatted(resp.statusCode(), body))))
                    .bodyToMono(Map.class)
                    .timeout(Duration.ofMillis(readTimeoutMs))
                    .onErrorMap(ex -> ex instanceof ModelServiceException
                            ? ex
                            : new ModelServiceException(
                                    "No fue posible ejecutar %s: %s".formatted(description,
                                            ex.getMessage()), ex))
                    .block();
            if (response == null) {
                throw new ModelServiceException("Respuesta vacía en " + description + ".");
            }
            return response;
        } catch (ModelServiceException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ModelServiceException(
                    "Error inesperado en %s: %s".formatted(description, ex.getMessage()), ex);
        }
    }

    /**
     * GET genérico hacia el microservicio ML que devuelve un mapa JSON.
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> getJson(String path, String description) {
        try {
            Map<String, Object> response = webClient.get()
                    .uri(path)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, resp -> resp.bodyToMono(String.class)
                            .defaultIfEmpty("")
                            .map(body -> new ModelServiceException(
                                    "El modelo respondió %s: %s".formatted(resp.statusCode(), body))))
                    .bodyToMono(Map.class)
                    .timeout(Duration.ofMillis(readTimeoutMs))
                    .onErrorMap(ex -> ex instanceof ModelServiceException
                            ? ex
                            : new ModelServiceException(
                                    "No fue posible obtener %s: %s".formatted(description,
                                            ex.getMessage()), ex))
                    .block();
            if (response == null) {
                throw new ModelServiceException("Respuesta vacía al obtener " + description + ".");
            }
            return response;
        } catch (ModelServiceException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ModelServiceException(
                    "Error inesperado obteniendo %s: %s".formatted(description, ex.getMessage()), ex);
        }
    }
}
