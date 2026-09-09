package com.bookrecommend.backend.model;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 模型推理服务客户端（算法侧与工程侧解耦）
 *
 * 通过 HTTP 调用 Python 侧的模型服务（FastAPI + ONNX + Faiss）：
 *  - /rank  : DeepFM 精排打分（输入含召回侧策略分）
 *  - /embed : 双塔用户向量 -> Faiss Top-100 语义召回
 * 调用失败由调用方降级为现有混合加权逻辑。
 */
@Slf4j
@Component
public class ModelServiceClient {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final long timeoutMs;
    private final boolean enabled;

    public ModelServiceClient(@Value("${model.service.base-url:http://localhost:8000}") String baseUrl,
                              @Value("${model.service.timeout-ms:3000}") long timeoutMs,
                              @Value("${model.service.enabled:true}") boolean enabled) {
        this.objectMapper = new ObjectMapper();
        this.baseUrl = baseUrl;
        this.timeoutMs = timeoutMs;
        this.enabled = enabled;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(timeoutMs))
                .build();
    }

    public boolean isEnabled() {
        return enabled;
    }

    /**
     * DeepFM 精排打分，返回 bookId -> sigmoid 分数
     */
    public Map<Long, Double> rank(Long userId, List<RankCandidate> candidates) throws Exception {
        ObjectNode body = objectMapper.createObjectNode();
        ArrayNode pairs = body.putArray("pairs");
        for (RankCandidate c : candidates) {
            pairs.addArray()
                    .add(userId).add(c.bookId())
                    .add(c.userCF()).add(c.itemCF()).add(c.content()).add(c.popular());
        }
        JsonNode resp = post("/rank", objectMapper.writeValueAsString(body));
        JsonNode scores = resp.get("scores");
        Map<Long, Double> result = new HashMap<>();
        for (int i = 0; i < candidates.size(); i++) {
            result.put(candidates.get(i).bookId(), scores.get(i).asDouble());
        }
        return result;
    }

    /**
     * 双塔语义召回：用户向量 -> Faiss 检索 Top-100
     */
    public List<Long> embed(Long userId) throws Exception {
        JsonNode resp = post("/embed", "{\"user_id\":" + userId + "}");
        JsonNode items = resp.get("items");
        List<Long> result = new ArrayList<>();
        items.forEach(n -> result.add(n.asLong()));
        return result;
    }

    /**
     * 自然语言找书（RAG）：查询向量化 -> 书籍向量余弦检索 Top-10
     */
    public List<Long> searchNL(String query) throws Exception {
        JsonNode resp = post("/search_nl",
                "{\"query\":" + objectMapper.writeValueAsString(query) + "}");
        JsonNode items = resp.get("items");
        List<Long> result = new ArrayList<>();
        items.forEach(n -> result.add(n.asLong()));
        return result;
    }

    private JsonNode post(String path, String jsonBody) throws Exception {
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + path))
                .timeout(Duration.ofMillis(timeoutMs))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                .build();
        HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
        if (resp.statusCode() != 200) {
            throw new IllegalStateException("model service status " + resp.statusCode());
        }
        return objectMapper.readTree(resp.body());
    }
}
