package com.highway.risk.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record AssessmentRequest(
        @JsonProperty("prepare_input") Boolean prepareInput,
        @JsonProperty("update_config") Boolean updateConfig,
        Boolean compare,
        Boolean recalculate
) {
    public AssessmentRequest {
        prepareInput = prepareInput == null ? Boolean.TRUE : prepareInput;
        updateConfig = updateConfig == null ? Boolean.FALSE : updateConfig;
        compare = compare == null ? Boolean.FALSE : compare;
        recalculate = recalculate == null ? Boolean.TRUE : recalculate;
        if (!recalculate && !compare) {
            throw new IllegalArgumentException("recalculate=false 时必须同时设置 compare=true");
        }
    }
}
