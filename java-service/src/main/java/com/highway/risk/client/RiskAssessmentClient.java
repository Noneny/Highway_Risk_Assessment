package com.highway.risk.client;

import com.highway.risk.dto.AssessmentRequest;
import com.highway.risk.dto.AssessmentTaskResponse;

/** Python 风险模型位于远程进程时的调用接口。 */
public interface RiskAssessmentClient {

    AssessmentTaskResponse submit(AssessmentRequest request);

    AssessmentTaskResponse get(String taskId);
}
