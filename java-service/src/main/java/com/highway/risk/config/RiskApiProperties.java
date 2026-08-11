package com.highway.risk.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "risk.api")
public record RiskApiProperties(String baseUrl, Duration connectTimeout, Duration readTimeout) {

    public RiskApiProperties {
        baseUrl = baseUrl == null ? "http://localhost:8000" : baseUrl;
        connectTimeout = connectTimeout == null ? Duration.ofSeconds(5) : connectTimeout;
        readTimeout = readTimeout == null ? Duration.ofSeconds(30) : readTimeout;
    }
}
