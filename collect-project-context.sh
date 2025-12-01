#!/bin/bash
# 프로젝트 정적 컨텍스트 수집 스크립트
# SessionStart 훅에서 호출되어 프로젝트 기본 정보를 수집

PROJECT_DIR="${1:-.}"
OUTPUT_FILE="$HOME/.claude/hooks/state/project-context.json"

cd "$PROJECT_DIR" 2>/dev/null || exit 0

# JSON 출력 시작
echo "{"

# Java 버전
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -1 | cut -d'"' -f2)
    echo "  \"java_version\": \"$JAVA_VERSION\","
fi

# Gradle 버전
if [ -f "gradle/wrapper/gradle-wrapper.properties" ]; then
    GRADLE_VERSION=$(grep "distributionUrl" gradle/wrapper/gradle-wrapper.properties | sed 's/.*gradle-\([0-9.]*\).*/\1/')
    echo "  \"gradle_version\": \"$GRADLE_VERSION\","
fi

# Maven 버전 (pom.xml에서)
if [ -f "pom.xml" ]; then
    echo "  \"build_tool\": \"maven\","
fi

# Spring Boot 버전
if [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
    SPRING_VERSION=$(grep -E "springBootVersion|spring-boot" build.gradle* 2>/dev/null | grep -oE "[0-9]+\.[0-9]+\.[0-9]+" | head -1)
    if [ -n "$SPRING_VERSION" ]; then
        echo "  \"spring_boot_version\": \"$SPRING_VERSION\","
    fi
fi

# Python 버전
if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        echo "  \"python_version\": \"$PYTHON_VERSION\","
    fi
fi

# Node.js 버전
if [ -f "package.json" ]; then
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version 2>&1)
        echo "  \"node_version\": \"$NODE_VERSION\","
    fi
fi

# DB 종류 추정 (application.yml/properties에서)
if [ -f "src/main/resources/application.yml" ]; then
    if grep -q "postgresql" "src/main/resources/application.yml"; then
        echo "  \"database\": \"postgresql\","
    elif grep -q "mysql" "src/main/resources/application.yml"; then
        echo "  \"database\": \"mysql\","
    elif grep -q "h2" "src/main/resources/application.yml"; then
        echo "  \"database\": \"h2\","
    fi
fi

# 프로젝트 구조
STRUCTURE="unknown"
if [ -d "src/main/java" ]; then
    STRUCTURE="java-maven-gradle"
elif [ -d "app" ] && [ -f "package.json" ]; then
    STRUCTURE="nextjs-or-node"
elif [ -d "src" ] && [ -f "package.json" ]; then
    STRUCTURE="typescript-or-react"
fi
echo "  \"project_structure\": \"$STRUCTURE\","

# 수집 시간
echo "  \"collected_at\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\""

echo "}"
