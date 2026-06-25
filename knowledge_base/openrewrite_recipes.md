# OpenRewrite Recipes for Java Migration

OpenRewrite provides automated refactoring recipes to safely perform large-scale upgrades.

## Standard Java Migration Recipes
- **`org.openrewrite.java.migrate.UpgradeToJava17`**: Upgrades a Java project to Java 17. It adjusts source compatibility settings, upgrades Maven/Gradle compilers and core plugins, replaces deprecated APIs, and adopts newer language patterns.
- **`org.openrewrite.java.migrate.UpgradeToJava21`**: Upgrades a Java project to Java 21. Upgrades Java build version, dependencies compatibility, and compiler release levels.
- **`org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta`**: Migrates import namespaces from `javax.*` to `jakarta.*` for JEE applications transitioning to Jakarta 9/10+.
- **`org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_0`**: Upgrades Spring Boot applications to Spring Boot 3.0, including Spring Security lambda configurations, properties renaming, and logging upgrades.

## Running OpenRewrite with Maven Plugin
Add the plugin configuration to the `pom.xml` build block, or execute it dynamically from the terminal:
```bash
mvn -U org.openrewrite.maven:rewrite-maven-plugin:run \
  -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:RELEASE,org.openrewrite.recipe:rewrite-spring:RELEASE \
  -Drewrite.activeRecipes=org.openrewrite.java.migrate.UpgradeToJava21
```

## Running OpenRewrite with Gradle Plugin
Configure the OpenRewrite plugin in your `build.gradle` file:
```groovy
plugins {
    id 'org.openrewrite.rewrite' version '6.8.2'
}

rewrite {
    activeRecipe 'org.openrewrite.java.migrate.UpgradeToJava21'
}

dependencies {
    rewrite 'org.openrewrite.recipe:rewrite-migrate-java:2.6.0'
}
```
Run the migration with:
```bash
./gradlew rewriteRun
```
