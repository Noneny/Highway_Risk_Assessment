package com.highway.risk.web;

import com.highway.risk.dto.AssessmentRequest;
import com.highway.risk.dto.AssessmentTaskResponse;
import com.highway.risk.service.RiskAssessmentService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/risk-assessments")
public class RiskAssessmentController {

    private final RiskAssessmentService service;

    public RiskAssessmentController(RiskAssessmentService service) {
        this.service = service;
    }

    @PostMapping
    public ResponseEntity<AssessmentTaskResponse> submit(@RequestBody AssessmentRequest request) {
        return ResponseEntity.accepted().body(service.submit(request));
    }

    @GetMapping("/{taskId}")
    public AssessmentTaskResponse get(@PathVariable String taskId) {
        return service.get(taskId);
    }
}
