package com.highway.risk.config;

import java.net.http.HttpClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration
public class RiskClientConfiguration {

    @Bean
    RestClient riskRestClient(RestClient.Builder builder, RiskApiProperties properties) {
        HttpClient httpClient = HttpClient.newBuilder()
                // Uvicorn does not accept the JDK client's clear-text HTTP/2 upgrade request
                // reliably; force HTTP/1.1 so the JSON body is parsed instead of reported missing.
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(properties.connectTimeout())
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(properties.readTimeout());

        return builder
                .baseUrl(properties.baseUrl())
                .requestFactory(requestFactory)
                .build();
    }
}
