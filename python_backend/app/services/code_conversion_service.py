import io
import zipfile
from typing import Dict, List
from app.models import ConversionResponse, ConvertedFile, AnalysisResponse
from app.ai.ai_factory import AIFactory

class CodeConversionService:
    def convert_files(self, files: Dict[str, str], api_key: str, model_name: str) -> ConversionResponse:
        system_instruction = (
            "You are an expert polyglot developer. Convert the provided Java code into modern Python. "
            "Maintain the exact same class structures, logic, and features. Use standard Python idioms (e.g. snake_case for methods, "
            "Pydantic for DTOs, FastAPI/Flask equivalents if Spring Boot is used). "
            "Your output MUST be strictly formatted with TWO sections:\n"
            "---EXPLANATION---\n"
            "(Brief explanation of changes)\n"
            "---CODE---\n"
            "(Only the raw Python code, no markdown code blocks)"
        )

        ai_client = AIFactory.get_client()
        converted_files = []
        
        for name, content in files.items():
            prompt = f"File: {name}\n\n```java\n{content}\n```\n\nConvert this to Python."
            try:
                ai_result = ai_client.generate(prompt, system_instruction, api_key, model_name)
                
                explanation = "Converted to Python."
                python_code = ai_result
                
                if "---CODE---" in ai_result:
                    parts = ai_result.split("---CODE---")
                    python_code = parts[1].strip()
                    if "---EXPLANATION---" in parts[0]:
                        explanation = parts[0].split("---EXPLANATION---")[1].strip()
                        
                # Remove markdown code blocks if the AI accidentally included them
                if python_code.startswith("```python"):
                    python_code = python_code[len("```python"):].strip()
                elif python_code.startswith("```"):
                    python_code = python_code[3:].strip()
                if python_code.endswith("```"):
                    python_code = python_code[:-3].strip()

                new_name = name.replace(".java", ".py")
                converted_files.append(
                    ConvertedFile(
                        originalName=name,
                        newName=new_name,
                        content=python_code,
                        explanation=explanation
                    )
                )
            except Exception as e:
                return ConversionResponse(
                    success=False,
                    errorMessage=f"Failed to convert {name}: {str(e)}"
                )
                
        return ConversionResponse(
            success=True,
            convertedFiles=converted_files
        )

    def package_python_zip(self, converted_files: List[ConvertedFile], analysis: AnalysisResponse) -> bytes:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in converted_files:
                zf.writestr(file.newName, file.content)
                
            # Add a requirements.txt if we have dependencies from analysis
            if analysis and analysis.dependencies:
                reqs = "# Auto-generated requirements based on Java dependencies\n"
                if "Spring Boot" in analysis.frameworks:
                    reqs += "fastapi\nuvicorn\npydantic\n"
                if any("hibernate" in d for d in analysis.dependencies):
                    reqs += "sqlalchemy\n"
                if any("jackson" in d for d in analysis.dependencies):
                    reqs += "pydantic\n"
                zf.writestr("requirements.txt", reqs)
                
            # Add a README
            readme = (
                "# Converted Python Project\n\n"
                "This project was converted from Java.\n\n"
                "## Running the code\n"
                "1. `pip install -r requirements.txt`\n"
                "2. `uvicorn main:app --reload` (If it is a FastAPI app)\n"
            )
            zf.writestr("README.md", readme)
            
        return zip_buffer.getvalue()

code_conversion_service = CodeConversionService()
