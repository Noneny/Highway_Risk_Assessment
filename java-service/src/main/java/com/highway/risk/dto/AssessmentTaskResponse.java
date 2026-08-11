package com.highway.risk.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record AssessmentTaskResponse(
        @JsonProperty("task_id") String taskId,
        String status,
        String phase,
        @JsonProperty("created_at") String createdAt,
        @JsonProperty("started_at") String startedAt,
        @JsonProperty("finished_at") String finishedAt,
        AssessmentResult result,
        String error
) {
    public record AssessmentResult(
            @JsonProperty("elapsed_seconds") Double elapsedSeconds,
            List<Artifact> artifacts
    ) {}

    public record Artifact(
            String kind,
            String path,
            @JsonProperty("size_bytes") Long sizeBytes,
            @JsonProperty("modified_at") String modifiedAt
    ) {}
}
