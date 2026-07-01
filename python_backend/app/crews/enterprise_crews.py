from crewai import Agent, Task, Crew, Process
from app.ai.langchain_wrapper import CustomRotatingChatModel
from typing import List

def get_crewai_llm():
    return CustomRotatingChatModel()

class EnterpriseCrews:
    def __init__(self):
        self.llm = get_crewai_llm()

    # =========================================================================
    # REPOSITORY ANALYSIS CREW
    # =========================================================================
    def run_repository_analysis_crew(self, project_dir: str) -> str:
        project_scanner = Agent(
            role='Project Scanner',
            goal='Scan the repository and identify all frameworks and configurations.',
            backstory='Expert in static analysis and project topography.',
            llm=self.llm
        )
        dependency_analyzer = Agent(
            role='Dependency Analyzer',
            goal='Analyze dependencies for compatibility and breaking changes.',
            backstory='DevOps guru handling Maven/Gradle builds.',
            llm=self.llm
        )
        architecture_analyzer = Agent(
            role='Architecture Analyzer',
            goal='Map out the microservice or monolith boundaries.',
            backstory='Principal Software Architect with 20 years experience.',
            llm=self.llm
        )
        manager = Agent(
            role='Manager Agent',
            goal='Synthesize findings into a Migration Plan.',
            backstory='Engineering Manager organizing migration tasks.',
            llm=self.llm
        )

        scan_task = Task(description=f'Scan {project_dir}', expected_output='Project Topography', agent=project_scanner)
        dep_task = Task(description=f'Analyze deps in {project_dir}', expected_output='Dep Issues', agent=dependency_analyzer)
        arch_task = Task(description=f'Map architecture of {project_dir}', expected_output='Arch Map', agent=architecture_analyzer)
        mgr_task = Task(description='Synthesize a final report', expected_output='Final Plan', agent=manager)

        crew = Crew(
            agents=[project_scanner, dependency_analyzer, architecture_analyzer, manager],
            tasks=[scan_task, dep_task, arch_task, mgr_task],
            process=Process.sequential
        )
        return str(crew.kickoff())

    # =========================================================================
    # BACKEND MIGRATION CREW
    # =========================================================================
    def run_backend_migration_crew(self, chunk_files: List[str]) -> str:
        architect = Agent(
            role='Spring Boot Architect',
            goal='Design the modern Spring Boot architecture for legacy classes.',
            backstory='Expert Java Architect transitioning monolithic legacy to Spring Boot 3.',
            llm=self.llm
        )
        api_generator = Agent(
            role='REST API Generator',
            goal='Convert Servlets/Struts to Spring REST Controllers.',
            backstory='API design specialist focused on standardizing endpoints.',
            llm=self.llm
        )
        
        task1 = Task(description=f'Analyze legacy classes: {chunk_files}', expected_output='Architecture Design', agent=architect)
        task2 = Task(description='Generate Spring Controllers and Services.', expected_output='Refactored Java Code', agent=api_generator)
        
        crew = Crew(agents=[architect, api_generator], tasks=[task1, task2], process=Process.sequential)
        return str(crew.kickoff())

    # =========================================================================
    # ERROR RECOVERY CREW
    # =========================================================================
    def run_error_recovery_crew(self, errors: str) -> str:
        agent = Agent(
            role='Error Recovery Specialist',
            goal='Analyze build/runtime errors and provide bash command fixes.',
            backstory='DevOps auto-healing bot.',
            llm=self.llm
        )
        task = Task(
            description=f'Errors:\n{errors}\nProvide bash commands to fix.',
            expected_output='Bash commands in ```bash code block.',
            agent=agent
        )
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
        return str(crew.kickoff())

enterprise_crews = EnterpriseCrews()
