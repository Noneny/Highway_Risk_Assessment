package com.highway.risk.service;

import com.highway.risk.client.RiskAssessmentClient;
import com.highway.risk.dto.AssessmentRequest;
import com.highway.risk.dto.AssessmentTaskResponse;
import org.springframework.stereotype.Service;

@Service
public class RiskAssessmentService {

    private final RiskAssessmentClient client;

    public RiskAssessmentService(RiskAssessmentClient client) {
        this.client = client;
    }

    public AssessmentTaskResponse submit(AssessmentRequest request) {
        return client.submit(request);
    }

    public AssessmentTaskResponse get(String taskId) {
        return client.get(taskId);
    }
}
