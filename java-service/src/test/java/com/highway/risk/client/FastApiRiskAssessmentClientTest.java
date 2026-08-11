package com.highway.risk.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.highway.risk.dto.AssessmentRequest;
import com.highway.risk.dto.AssessmentTaskResponse;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class FastApiRiskAssessmentClientTest {

    @Test
    void submitsSnakeCasePayloadAndMapsTaskResponse() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://risk-api:8000");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        FastApiRiskAssessmentClient client = new FastApiRiskAssessmentClient(builder.build());

        server.expect(requestTo("http://risk-api:8000/api/v1/assessments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().json("""
                        {
                          "prepare_input": true,
                          "update_config": false,
                          "compare": false,
                          "recalculate": true
                        }
                        """))
                .andRespond(withSuccess("""
                        {
                          "task_id": "task-42",
                          "status": "QUEUED",
                          "phase": "QUEUED",
                          "created_at": "2026-08-11T09:00:00Z",
                          "started_at": null,
                          "finished_at": null,
                          "result": null,
                          "error": null
                        }
                        """, MediaType.APPLICATION_JSON));

        AssessmentTaskResponse response = client.submit(
                new AssessmentRequest(true, false, false, true)
        );

        assertThat(response.taskId()).isEqualTo("task-42");
        assertThat(response.status()).isEqualTo("QUEUED");
        server.verify();
    }
}
