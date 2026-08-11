package com.highway.risk.client;

import com.highway.risk.dto.AssessmentRequest;
import com.highway.risk.dto.AssessmentTaskResponse;
import java.util.Objects;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class FastApiRiskAssessmentClient implements RiskAssessmentClient {

    private final RestClient restClient;

    public FastApiRiskAssessmentClient(RestClient riskRestClient) {
        this.restClient = riskRestClient;
    }

    @Override
    public AssessmentTaskResponse submit(AssessmentRequest request) {
        return Objects.requireNonNull(restClient.post()
                .uri("/api/v1/assessments")
                .body(request)
                .retrieve()
                .body(AssessmentTaskResponse.class), "Python服务返回了空响应");
    }

    @Override
    public AssessmentTaskResponse get(String taskId) {
        return Objects.requireNonNull(restClient.get()
                .uri("/api/v1/assessments/{taskId}", taskId)
                .retrieve()
                .body(AssessmentTaskResponse.class), "Python服务返回了空响应");
    }
}
