# Spring Boot 3 Migration Guide

Upgrading to Spring Boot 3.x is a critical milestone that requires Java 17 as the baseline version, with support for Java 21.

## Major Changes in Spring Boot 3.x
1. **Jakarta EE 10 Transition**: The package namespace changed from `javax.*` to `jakarta.*` for all Java EE specifications (e.g. Servlet API, JPA, Bean Validation, JAXB).
   - *Example*: `javax.persistence.Entity` becomes `jakarta.persistence.Entity`.
   - *Example*: `javax.servlet.http.HttpServletRequest` becomes `jakarta.servlet.http.HttpServletRequest`.
2. **Spring Security 6.0**: Web security configuration class structure has changed. `WebSecurityConfigurerAdapter` is removed.
   - Use `SecurityFilterChain` bean definitions and standard lambda configurations for configuring security rules:
     ```java
     @Bean
     public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
         http
             .authorizeHttpRequests(auth -> auth
                 .requestMatchers("/api/public/**").permitAll()
                 .anyRequest().authenticated()
             );
         return http.build();
     }
     ```
3. **Observation Registry**: Spring Boot 3 replaces old metrics instrumentation with Micrometer Observation API, consolidating logging, tracing, and metrics collection.

## Upgrading Strategy
- **Step 1**: Ensure your project is running on Spring Boot 2.7.x and Java 11 or 17.
- **Step 2**: Replace `javax` import namespaces with `jakarta`.
- **Step 3**: Change Spring Boot parent version in `pom.xml` to `3.x.y` (e.g., `3.2.5`).
- **Step 4**: Upgrade Spring Security declarations to use component-based config.
- **Step 5**: Update database driver configurations, as Spring Boot 3 uses Hibernate 6 which requires updated dialects and properties.
- **Step 6**: Execute Maven verification (`mvn clean verify`) to catch compilation or testing breaks.
