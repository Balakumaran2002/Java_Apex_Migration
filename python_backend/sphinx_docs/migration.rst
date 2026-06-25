Migration Status Report
=======================

**success**

  True

**targetVersion**

  17

**modifiedFiles**

  - pom.xml
  - src/main/java/com/employee/system/service/DocumentService.java
  - target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst
  - target/maven-status/maven-compiler-plugin/compile/default-compile/inputFiles.lst

**buildStatus**

  Build Success

**suggestedFixes**

  None

**detailedReport**

  {
  "accuracy": 99,
  "percentage_migrated": 100,
  "files": [
    {
      "filename": "pom.xml",
      "before_code": "<parent>\n\t\t<groupId>org.springframework.boot</groupId>\n\t\t<artifactId>spring-boot-starter-parent</artifactId>\n\t\t<version>2.7.12</version>\n\t\t<relativePath/> <!-- lookup parent from repository -->\n\t</parent>\n\t<groupId>com.employee</groupId>\n...\n\t<properties>\n\t\t<java.version>8</java.version>\n\t\t<lombok.version>1.18.28</lombok.version>\n\t\t<maven.compiler.source>8</maven.compiler.source>\n\t\t<maven.compiler.target>8</maven.compiler.target>\n\t</properties>\n\t<dependencies>\n\t\t<dependency>\n\t\t\t<groupId>org.springframework.boot</groupId>\n\t\t\t<artifactId>spring-boot-starter-data-jpa</artifactId>\n\t\t</dependency>\n\t\t<dependency>\n\t\t\t<groupId>org.springframework.boot</groupId>\n\t\t\t<artifactId>spring-boot-starter-web</artifactId>\n\t\t</dependency>\n\t\t<dependency>\n\t\t\t<groupId>org.projectlombok</groupId>\n\t\t\t<artifactId>lombok</artifactId>\n\t\t\t<version>${lombok.version}</version>\n\t\t\t<optional>true</optional>\n\t\t</dependency>\n...\n\t\t\t\t<groupId>org.apache.maven.plugins</groupId>\n\t\t\t\t<artifactId>maven-compiler-plugin</artifactId>\n\t\t\t\t<configuration>\n\t\t\t\t\t<source>8</source>\n\t\t\t\t\t<target>8</target>\n\t\t\t\t\t<release>8</release>",
      "after_code": "<parent>\n\t\t<groupId>org.springframework.boot</groupId>\n\t\t<artifactId>spring-boot-starter-parent</artifactId>\n\t\t<version>3.2.12</version>\n\t\t<relativePath/> <!-- lookup parent from repository -->\n\t</parent>\n\t<groupId>com.employee</groupId>\n...\n\t<properties>\n\t\t<java.version>17</java.version>\n\t\t<lombok.version>1.18.46</lombok.version>\n\t</properties>\n\t<dependencies>\n\t\t<dependency>\n\t\t\t<groupId>org.springframework.boot</groupId>\n\t\t\t<artifactId>spring-boot-starter-data-jpa</artifactId>\n\t\t</dependency>\n\t\t<dependency>\n\t\t\t<groupId>org.springframework.boot</groupId>\n\t\t\t<artifactId>spring-boot-starter-web</artifactId>\n\t\t</dependency>\n\t\t<dependency>\n\t\t\t<groupId>org.projectlombok</groupId>\n\t\t\t<artifactId>lombok</artifactId>\n\t\t\t<optional>true</optional>\n\t\t</dependency>\n...\n\t\t\t\t<groupId>org.apache.maven.plugins</groupId>\n\t\t\t\t<artifactId>maven-compiler-plugin</artifactId>\n\t\t\t\t<configuration>\n\t\t\t\t\t<release>${java.version}</release>",
      "explanation": "This file was updated to migrate the project to Spring Boot 3.2.12, which necessitated an upgrade of the Java version from 8 to 17. The Lombok dependency version was also updated from 1.18.28 to 1.18.46. The Maven compiler plugin configuration was modernized by removing explicit `source` and `target` versions and using the `release` property tied to the `java.version` property. The explicit version tag for Lombok was removed from its dependency declaration, relying on property management or parent POM inheritance."
    },
    {
      "filename": "src/main/java/com/employee/system/service/DocumentService.java",
      "before_code": "import java.io.IOException;\nimport javax.annotation.PostConstruct;\nimport java.net.MalformedURLException;\nimport java.nio.file.Files;\nimport java.nio.file.Path;\nimport java.nio.file.Paths;\nimport java.nio.file.StandardCopyOption;\nimport java.time.LocalDate;\n...\n    private final DocumentRepository documentRepository;\n    private final EmployeeRepository employeeRepository;\n\n    private final Path uploadsDir = Paths.get(\"uploads\");\n\n    @PostConstruct\n    public void init() {\n...\n    private String sanitizeFilename(String name) {\n        if (name == null) return \"unnamed\";\n        return Paths.get(name).getFileName().toString().replaceAll(\"[^a-zA-Z0-9._-]\", \"_\");\n    }",
      "after_code": "import java.io.IOException;\nimport jakarta.annotation.PostConstruct;\nimport java.net.MalformedURLException;\nimport java.nio.file.Files;\nimport java.nio.file.Path;\nimport java.nio.file.StandardCopyOption;\nimport java.time.LocalDate;\n...\n    private final DocumentRepository documentRepository;\n    private final EmployeeRepository employeeRepository;\n\n    private final Path uploadsDir = Path.of(\"uploads\");\n\n    @PostConstruct\n    public void init() {\n...\n    private String sanitizeFilename(String name) {\n        if (name == null) return \"unnamed\";\n        return Path.of(name).getFileName().toString().replaceAll(\"[^a-zA-Z0-9._-]\", \"_\");\n    }",
      "explanation": "The `javax.annotation.PostConstruct` import was migrated to `jakarta.annotation.PostConstruct` to align with Jakarta EE 9+, which is a requirement for Spring Boot 3. Additionally, the usage of `java.nio.file.Paths.get()` was replaced with the more concise `java.nio.file.Path.of()` method, a modern Java API usage introduced in Java 11."
    }
  ],
  "dependencies": [
    {
      "name": "org.springframework.boot:spring-boot-starter-parent",
      "old_version": "2.7.12",
      "new_version": "3.2.12",
      "reason": "Major upgrade to Spring Boot 3.x, which brings significant changes including a baseline Java 17 requirement and migration to Jakarta EE."
    },
    {
      "name": "Java Development Kit (JDK)",
      "old_version": "8",
      "new_version": "17",
      "reason": "Required for Spring Boot 3.x compatibility. Spring Boot 3.x applications must run on Java 17 or higher."
    },
    {
      "name": "org.projectlombok:lombok",
      "old_version": "1.18.28",
      "new_version": "1.18.46",
      "reason": "Upgrade to a newer version of Lombok for compatibility and latest features, often recommended when upgrading Spring Boot and Java versions."
    },
    {
      "name": "Maven Compiler Plugin Configuration",
      "old_version": "source=8, target=8, release=8",
      "new_version": "release=${java.version}",
      "reason": "Modernization of Maven compiler plugin configuration to use the `release` flag, aligning with the upgraded Java 17 version and simplifying configuration."
    },
    {
      "name": "Jakarta EE API (javax.annotation to jakarta.annotation)",
      "old_version": "javax.annotation",
      "new_version": "jakarta.annotation",
      "reason": "Spring Boot 3.x and above migrate from Java EE (javax.*) to Jakarta EE (jakarta.*) namespaces. This requires updating imports for annotations like @PostConstruct."
    }
  ]
}

**buildErrors**

  None

**migrationSummary**

  
--- Starting Migration ---
[INFO] Scanning for projects...
[INFO]
[INFO] Using the MultiThreadedBuilder implementation with a thread count of 8
[INFO]
[INFO] ------------------------< com.employee:system >-------------------------
[INFO] Building  0.0.1-SNAPSHOT
[INFO]   from pom.xml
[INFO] --------------------------------[ jar ]---------------------------------
[INFO]
[INFO] >>> rewrite:6.41.0:run (default-cli) > process-test-classes @ system >>>
[INFO]
[INFO] --- resources:3.2.0:resources (default-resources) @ system ---
[INFO] Using 'UTF-8' encoding to copy filtered resources.
[INFO] Using 'UTF-8' encoding to copy filtered properties files.
[INFO] Copying 1 resource
[INFO] Copying 0 resource
[INFO]
[INFO] --- compiler:3.10.1:compile (default-compile) @ system ---
[INFO] Changes detected - recompiling the module!
[INFO] Compiling 63 source files to C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\target\classes
[INFO]
[INFO] --- resources:3.2.0:testResources (default-testResources) @ system ---
[INFO] Not copying test resources
[INFO]
[INFO] --- compiler:3.10.1:testCompile (default-testCompile) @ system ---
[INFO] Not compiling test sources
[INFO]
[INFO] <<< rewrite:6.41.0:run (default-cli) < process-test-classes @ system <<<
[INFO]
[INFO]
[INFO] --- rewrite:6.41.0:run (default-cli) @ system ---
[INFO] Using active recipe(s) [org.openrewrite.java.migrate.UpgradeToJava17, org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_2]
[INFO] Using active styles(s) []
[INFO] Downloading from central: https://repo.maven.apache.org/maven2/org/openrewrite/recipe/rewrite-migrate-java/maven-metadata.xml
[INFO] Downloaded from central: https://repo.maven.apache.org/maven2/org/openrewrite/recipe/rewrite-migrate-java/maven-metadata.xml (5.0 kB at 4.9 kB/s)
[INFO] Downloading from central: https://repo.maven.apache.org/maven2/org/openrewrite/recipe/rewrite-spring/maven-metadata.xml
[INFO] Downloaded from central: https://repo.maven.apache.org/maven2/org/openrewrite/recipe/rewrite-spring/maven-metadata.xml (5.4 kB at 19 kB/s)
[INFO] Validating active recipes...
[INFO] Project [] Resolving Poms...
[INFO] Project [] Parsing source files
[INFO] Running recipe(s)...
[WARNING] Changes have been made to pom.xml by:
[WARNING]     org.openrewrite.java.migrate.UpgradeToJava17
[WARNING]         org.openrewrite.java.migrate.Java8toJava11
[WARNING]             org.openrewrite.java.migrate.lombok.UpdateLombokToJava11
[WARNING]                 org.openrewrite.java.dependencies.UpgradeDependencyVersion
[WARNING]         org.openrewrite.java.migrate.UpgradeBuildToJava17
[WARNING]             org.openrewrite.java.migrate.UpgradeJavaVersion
[WARNING]                 org.openrewrite.maven.UseMavenCompilerPluginReleaseConfiguration
[WARNING]         org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_2
[WARNING]             org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_1
[WARNING]                 org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_0
[WARNING]                     org.openrewrite.java.spring.boot2.UpgradeSpringBoot_2_7
[WARNING]                         org.openrewrite.maven.UpgradeParentVersion
[WARNING]                     org.openrewrite.maven.UpgradeParentVersion
[WARNING]                 org.openrewrite.maven.UpgradeParentVersion
[WARNING]             org.openrewrite.maven.UpgradeParentVersion: {groupId=org.springframework.boot, artifactId=spring-boot-starter-parent, newVersion=3.2.x}
[WARNING] Changes have been made to src\main\java\com\employee\system\service\DocumentService.java by:
[WARNING]     org.openrewrite.java.migrate.UpgradeToJava17
[WARNING]         org.openrewrite.java.migrate.Java8toJava11
[WARNING]             org.openrewrite.java.migrate.nio.file.PathsGetToPathOf
[WARNING]                 org.openrewrite.java.ChangeMethodTargetToStatic
[WARNING]                 org.openrewrite.java.ChangeMethodName
[WARNING]         org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_2
[WARNING]             org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_1
[WARNING]                 org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_0
[WARNING]                     org.openrewrite.java.spring.framework.UpgradeSpringFramework_6_0
[WARNING]                         org.openrewrite.java.migrate.jakarta.JakartaEE10
[WARNING]                             org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta
[WARNING]                                 org.openrewrite.java.migrate.jakarta.JavaxAnnotationMigrationToJakartaAnnotation
[WARNING]                                     org.openrewrite.java.ChangePackage
[WARNING] Please review and commit the results.
[WARNING] Estimate time saved: 45m
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
[INFO] Total time:  01:20 min (Wall Clock)
[INFO] Finished at: 2026-06-20T00:19:38+05:30
[INFO] ------------------------------------------------------------------------

**errorMessage**

  None

**gitDiff**

  diff --git a/pom.xml b/pom.xml
index 7cd1a07..5ede99f 100644
--- a/pom.xml
+++ b/pom.xml
@@ -5,7 +5,7 @@
 	<parent>
 		<groupId>org.springframework.boot</groupId>
 		<artifactId>spring-boot-starter-parent</artifactId>
-		<version>2.7.12</version>
+		<version>3.2.12</version>
 		<relativePath/> <!-- lookup parent from repository -->
 	</parent>
 	<groupId>com.employee</groupId>
@@ -27,10 +27,8 @@
 		<url/>
 	</scm>
 	<properties>
-		<java.version>8</java.version>
-		<lombok.version>1.18.28</lombok.version>
-		<maven.compiler.source>8</maven.compiler.source>
-		<maven.compiler.target>8</maven.compiler.target>
+		<java.version>17</java.version>
+		<lombok.version>1.18.46</lombok.version>
 	</properties>
 	<dependencies>
 		<dependency>
@@ -44,7 +42,6 @@
 		<dependency>
 			<groupId>org.projectlombok</groupId>
 			<artifactId>lombok</artifactId>
-			<version>${lombok.version}</version>
 			<optional>true</optional>
 		</dependency>
 		<dependency>
@@ -91,9 +88,7 @@
 				<groupId>org.apache.maven.plugins</groupId>
 				<artifactId>maven-compiler-plugin</artifactId>
 				<configuration>
-					<source>8</source>
-					<target>8</target>
-					<release>8</release>
+					<release>${java.version}</release>
 					<fork>true</fork>
 					<annotationProcessorPaths>
 						<path>
diff --git a/src/main/java/com/employee/system/service/DocumentService.java b/src/main/java/com/employee/system/service/DocumentService.java
index 86e497a..1b53860 100644
--- a/src/main/java/com/employee/system/service/DocumentService.java
+++ b/src/main/java/com/employee/system/service/DocumentService.java
@@ -13,11 +13,10 @@ import org.springframework.transaction.annotation.Transactional;
 import org.springframework.web.multipart.MultipartFile;
 
 import java.io.IOException;
-import javax.annotation.PostConstruct;
+import jakarta.annotation.PostConstruct;
 import java.net.MalformedURLException;
 import java.nio.file.Files;
 import java.nio.file.Path;
-import java.nio.file.Paths;
 import java.nio.file.StandardCopyOption;
 import java.time.LocalDate;
 import java.util.List;
@@ -32,7 +31,7 @@ public class DocumentService {
     private final DocumentRepository documentRepository;
     private final EmployeeRepository employeeRepository;
 
-    private final Path uploadsDir = Paths.get("uploads");
+    private final Path uploadsDir = Path.of("uploads");
 
     @PostConstruct
     public void init() {
@@ -87,7 +86,7 @@ public class DocumentService {
 
     private String sanitizeFilename(String name) {
         if (name == null) return "unnamed";
-        return Paths.get(name).getFileName().toString().replaceAll("[^a-zA-Z0-9._-]", "_");
+        return Path.of(name).getFileName().toString().replaceAll("[^a-zA-Z0-9._-]", "_");
     }
 
     private DocumentDTO toDTO(Document d) {
diff --git a/target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst b/target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst
index e69de29..65e34cb 100644
--- a/target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst
+++ b/target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst
@@ -0,0 +1,64 @@
+com\employee\system\entity\RatingScale.class
+com\employee\system\response\ApiResponse.class
+com\employee\system\dto\SalaryDTO.class
+com\employee\system\controller\ManagerFeedbackController.class
+com\employee\system\entity\Document.class
+com\employee\system\dto\LeaveDTO.class
+com\employee\system\service\RatingScaleService.class
+com\employee\system\controller\LeaveController.class
+com\employee\system\service\EmployeeService.class
+com\employee\system\SystemApplication.class
+com\employee\system\service\PerformanceReviewService.class
+com\employee\system\repository\SalaryRepository.class
+com\employee\system\controller\PerformanceGoalController.class
+com\employee\system\controller\PerformanceReviewController.class
+com\employee\system\service\AttendanceSummary$AttendanceSummaryBuilder.class
+com\employee\system\dto\LeaveBalanceDTO.class
+com\employee\system\dto\PerformanceReviewDTO.class
+com\employee\system\controller\KPIController.class
+com\employee\system\entity\PerformanceGoal.class
+com\employee\system\repository\HolidayRepository.class
+com\employee\system\repository\PerformanceGoalRepository.class
+com\employee\system\service\AttendanceService.class
+com\employee\system\dto\SelfAssessmentDTO.class
+com\employee\system\repository\KPIRepository.class
+com\employee\system\entity\Employee.class
+com\employee\system\service\SelfAssessmentService.class
+com\employee\system\dto\RatingScaleDTO.class
+com\employee\system\service\PerformanceGoalService.class
+com\employee\system\controller\RatingScaleController.class
+com\employee\system\repository\RatingScaleRepository.class
+com\employee\system\entity\PerformanceReview.class
+com\employee\system\entity\SelfAssessment.class
+com\employee\system\controller\AttendanceController.class
+com\employee\system\service\KPIService.class
+com\employee\system\controller\SelfAssessmentController.class
+com\employee\system\entity\Salary.class
+com\employee\system\dto\DocumentDTO.class
+com\employee\system\dto\KPIDTO.class
+com\employee\system\repository\PerformanceReviewRepository.class
+com\employee\system\repository\EmployeeRepository.class
+com\employee\system\service\AttendanceSummary.class
+com\employee\system\controller\SalaryController.class
+com\employee\system\entity\Holiday.class
+com\employee\system\repository\LeaveRepository.class
+com\employee\system\repository\DocumentRepository.class
+com\employee\system\repository\ManagerFeedbackRepository.class
+com\employee\system\dto\AttendanceDTO.class
+com\employee\system\dto\EmployeeDTO.class
+com\employee\system\dto\PerformanceGoalDTO.class
+com\employee\system\entity\Attendance.class
+com\employee\system\service\SalaryService.class
+com\employee\system\repository\AttendanceRepository.class
+com\employee\system\exception\ErrorResponse.class
+com\employee\system\service\LeaveService.class
+com\employee\system\controller\EmployeeController.class
+com\employee\system\entity\Leave.class
+com\employee\system\service\ManagerFeedbackService.class
+com\employee\system\entity\KPI.class
+com\employee\system\controller\DocumentController.class
+com\employee\system\entity\ManagerFeedback.class
+com\employee\system\repository\SelfAssessmentRepository.class
+com\employee\system\dto\ManagerFeedbackDTO.class
+com\employee\system\exception\GlobalExceptionHandler.class
+com\employee\system\service\DocumentService.class
diff --git a/target/maven-status/maven-compiler-plugin/compile/default-compile/inputFiles.lst b/target/maven-status/maven-compiler-plugin/compile/default-compile/inputFiles.lst
index 3872e36..bc05e75 100644
--- a/target/maven-status/maven-compiler-plugin/compile/default-compile/inputFiles.lst
+++ b/target/maven-status/maven-compiler-plugin/compile/default-compile/inputFiles.lst
@@ -1,63 +1,63 @@
-C:\TestProject\system\src\main\java\com\employee\system\service\SalaryService.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\KPIRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\Holiday.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\ManagerFeedbackController.java
-C:\TestProject\system\src\main\java\com\employee\system\service\AttendanceService.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\SalaryController.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\EmployeeDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\SelfAssessmentRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\service\PerformanceReviewService.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\KPIController.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\LeaveDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\KPIDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\KPI.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\ManagerFeedback.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\RatingScale.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\AttendanceRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\PerformanceGoal.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\Employee.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\LeaveController.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\SelfAssessmentController.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\Salary.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\PerformanceReviewDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\DocumentRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\RatingScaleDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\ManagerFeedbackRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\Document.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\SelfAssessment.java
-C:\TestProject\system\src\main\java\com\employee\system\response\ApiResponse.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\EmployeeRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\EmployeeController.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\ManagerFeedbackDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\PerformanceGoalDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\Attendance.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\DocumentController.java
-C:\TestProject\system\src\main\java\com\employee\system\service\ManagerFeedbackService.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\LeaveBalanceDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\PerformanceReviewRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\service\LeaveService.java
-C:\TestProject\system\src\main\java\com\employee\system\exception\GlobalExceptionHandler.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\AttendanceDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\PerformanceGoalController.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\Leave.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\RatingScaleController.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\SalaryDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\entity\PerformanceReview.java
-C:\TestProject\system\src\main\java\com\employee\system\service\DocumentService.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\DocumentDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\service\PerformanceGoalService.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\PerformanceGoalRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\exception\ErrorResponse.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\SalaryRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\AttendanceController.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\HolidayRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\service\AttendanceSummary.java
-C:\TestProject\system\src\main\java\com\employee\system\dto\SelfAssessmentDTO.java
-C:\TestProject\system\src\main\java\com\employee\system\SystemApplication.java
-C:\TestProject\system\src\main\java\com\employee\system\controller\PerformanceReviewController.java
-C:\TestProject\system\src\main\java\com\employee\system\service\EmployeeService.java
-C:\TestProject\system\src\main\java\com\employee\system\service\SelfAssessmentService.java
-C:\TestProject\system\src\main\java\com\employee\system\service\RatingScaleService.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\RatingScaleRepository.java
-C:\TestProject\system\src\main\java\com\employee\system\service\KPIService.java
-C:\TestProject\system\src\main\java\com\employee\system\repository\LeaveRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\KPIDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\LeaveController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\RatingScaleRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\AttendanceSummary.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\PerformanceGoalDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\ManagerFeedbackService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\AttendanceController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\PerformanceReviewRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\LeaveRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\SalaryService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\ManagerFeedbackController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\ManagerFeedbackRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\Leave.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\SelfAssessment.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\EmployeeRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\DocumentDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\ManagerFeedbackDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\EmployeeController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\Document.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\EmployeeService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\PerformanceGoalService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\KPI.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\SelfAssessmentDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\HolidayRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\SystemApplication.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\Salary.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\PerformanceGoalRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\PerformanceReviewService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\SalaryDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\PerformanceGoal.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\LeaveService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\RatingScaleController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\exception\GlobalExceptionHandler.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\PerformanceReviewController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\SalaryController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\RatingScaleService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\AttendanceRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\EmployeeDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\SelfAssessmentRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\DocumentRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\PerformanceGoalController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\DocumentController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\Attendance.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\KPIService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\PerformanceReview.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\RatingScaleDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\Holiday.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\SelfAssessmentService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\LeaveBalanceDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\PerformanceReviewDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\AttendanceService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\AttendanceDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\Employee.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\dto\LeaveDTO.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\KPIRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\KPIController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\response\ApiResponse.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\ManagerFeedback.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\repository\SalaryRepository.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\controller\SelfAssessmentController.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\service\DocumentService.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\entity\RatingScale.java
+C:\Users\ST-HarishR\Desktop\Projects\convertion\java_convertion\java_convertion\python_backend\workspace\EMS\src\main\java\com\employee\system\exception\ErrorResponse.java


**fixHistory**


**usedProvider**

  gemini

