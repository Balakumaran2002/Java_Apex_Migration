# Java 21 Migration Guide

Java 21 is a Long Term Support (LTS) release packed with major enhancements, particularly around concurrency and data patterns.

## Key Java 21 Language Features
- **Virtual Threads (Project Loom)**: Lightweight threads that reduce the effort of writing, maintaining, and observing high-throughput concurrent applications. They allow scaling thread count to millions.
- **Sequenced Collections**: Introduces new interfaces representing collections with a defined encounter order (e.g. `SequencedCollection`, `SequencedSet`, `SequencedMap`) with standard methods like `addFirst`, `addLast`, `getFirst`, `getLast`, `reversed`.
- **Pattern Matching for Switch**: Enables switch expressions to check patterns: `switch (obj) { case Integer i -> ... case String s -> ... }`.
- **Record Patterns**: Deconstructs record values: `if (obj instanceof Point(int x, int y)) { ... }`.
- **String Templates (Preview in 21)**: Simplified string interpolation using standard template processors.

## Migrating to Java 21
1. **Garbage Collection (ZGC)**: Generational ZGC is introduced in Java 21, providing extremely low latency (sub-millisecond pause times) for large heaps. Enable via `-XX:+UseZGC -XX:+ZGenerational`.
2. **Build Configuration**:
   - Update Maven `pom.xml` configuration for compiler release:
     ```xml
     <properties>
         <maven.compiler.release>21</maven.compiler.release>
     </properties>
     ```
   - For Gradle:
     ```groovy
     java {
         toolchain {
             languageVersion = JavaLanguageVersion.of(21)
         }
     }
     ```
3. **Third-Party Dependency Upgrades**: Libraries like Spring, Hibernate, ByteBuddy, Mockito, and Lombok must be upgraded to versions compatible with Java 21 runtime class file structures.
