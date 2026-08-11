package com.highway.risk.web;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

@RestControllerAdvice
public class IntegrationExceptionHandler {

    @ExceptionHandler(IllegalArgumentException.class)
    ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException exception) {
        return ResponseEntity.badRequest().body(Map.of("error", exception.getMessage()));
    }

    @ExceptionHandler(RestClientResponseException.class)
    ResponseEntity<Map<String, String>> handlePythonApiError(RestClientResponseException exception) {
        HttpStatus status = HttpStatus.resolve(exception.getStatusCode().value());
        HttpStatus responseStatus = status == HttpStatus.NOT_FOUND
                ? HttpStatus.NOT_FOUND
                : HttpStatus.BAD_GATEWAY;
        return ResponseEntity.status(responseStatus).body(Map.of(
                "error", "Python风险评估服务调用失败",
                "detail", exception.getResponseBodyAsString()
        ));
    }

    @ExceptionHandler(RestClientException.class)
    ResponseEntity<Map<String, String>> handlePythonApiUnavailable(RestClientException exception) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
                "error", "Python风险评估服务不可用",
                "detail", exception.getMessage()
        ));
    }
}
