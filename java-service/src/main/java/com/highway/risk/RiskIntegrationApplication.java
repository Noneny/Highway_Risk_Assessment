package com.highway.risk;

import com.highway.risk.config.RiskApiProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties(RiskApiProperties.class)
public class RiskIntegrationApplication {

    public static void main(String[] args) {
        SpringApplication.run(RiskIntegrationApplication.class, args);
    }
}
