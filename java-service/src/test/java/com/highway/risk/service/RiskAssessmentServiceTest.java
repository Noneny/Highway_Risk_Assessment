package com.highway.risk.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.highway.risk.client.RiskAssessmentClient;
import com.highway.risk.dto.AssessmentRequest;
import com.highway.risk.dto.AssessmentTaskResponse;
import org.junit.jupiter.api.Test;

class RiskAssessmentServiceTest {

    @Test
    void delegatesSubmissionThroughClientInterface() {
        AssessmentTaskResponse expected = new AssessmentTaskResponse(
                "task-1", "QUEUED", "QUEUED", "2026-08-11T00:00:00Z",
                null, null, null, null
        );
        RiskAssessmentClient fakeClient = new RiskAssessmentClient() {
            @Override
            public AssessmentTaskResponse submit(AssessmentRequest request) {
                return expected;
            }

            @Override
            public AssessmentTaskResponse get(String taskId) {
                return expected;
            }
        };

        RiskAssessmentService service = new RiskAssessmentService(fakeClient);

        assertThat(service.submit(new AssessmentRequest(true, false, false, true)))
                .isSameAs(expected);
        assertThat(service.get("task-1")).isSameAs(expected);
    }
}
