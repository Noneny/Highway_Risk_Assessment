package com.highway.risk.config;

import static org.assertj.core.api.Assertions.assertThat;

import com.highway.risk.client.FastApiRiskAssessmentClient;
import com.highway.risk.dto.AssessmentRequest;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

class RiskClientConfigurationTest {

    @Test
    void sendsJsonWithoutH2cUpgradeHeaders() throws Exception {
        AtomicReference<String> requestBody = new AtomicReference<>();
        AtomicReference<String> upgradeHeader = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/v1/assessments", exchange -> {
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            upgradeHeader.set(exchange.getRequestHeaders().getFirst("Upgrade"));
            byte[] response = """
                    {
                      "task_id": "transport-test",
                      "status": "QUEUED",
                      "phase": "QUEUED",
                      "created_at": "2026-08-11T10:00:00Z",
                      "started_at": null,
                      "finished_at": null,
                      "result": null,
                      "error": null
                    }
                    """.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(202, response.length);
            exchange.getResponseBody().write(response);
            exchange.close();
        });
        server.start();

        try {
            String baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
            RiskApiProperties properties = new RiskApiProperties(
                    baseUrl, Duration.ofSeconds(2), Duration.ofSeconds(5)
            );
            RestClient restClient = new RiskClientConfiguration()
                    .riskRestClient(RestClient.builder(), properties);

            new FastApiRiskAssessmentClient(restClient).submit(
                    new AssessmentRequest(true, true, true, true)
            );

            assertThat(requestBody.get()).contains("\"prepare_input\":true");
            assertThat(upgradeHeader.get()).isNull();
        } finally {
            server.stop(0);
        }
    }
}
