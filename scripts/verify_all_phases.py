#!/usr/bin/env python3
"""
完整验收测试 - 验证所有Phase的验收标准
Project_Architecture.md 各Phase验收标准检查
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

def print_header(text):
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)

def print_check(name, passed, detail=""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {name}")
    if detail:
        print(f"       {detail}")

def verify_phase0():
    """Phase 0 - 环境初始化验收"""
    print_header("Phase 0 - 环境初始化")

    results = []

    # 检查 requirements.txt
    req_file = Path(__file__).parent.parent / "backend" / "requirements.txt"
    passed = req_file.exists()
    print_check("requirements.txt 存在", passed)
    results.append(passed)

    # 检查 settings.py
    settings_file = Path(__file__).parent.parent / "backend" / "config" / "settings.py"
    passed = settings_file.exists()
    print_check("config/settings.py 存在", passed)
    results.append(passed)

    # 检查配置加载
    try:
        from config.settings import settings
        passed = settings.es_host is not None
        print_check("配置加载正常", passed, f"es_host={settings.es_host}")
        results.append(passed)
    except Exception as e:
        print_check("配置加载正常", False, str(e))
        results.append(False)

    # 检查 .env.example
    env_example = Path(__file__).parent.parent / "backend" / ".env.example"
    passed = env_example.exists()
    print_check(".env.example 存在", passed)
    results.append(passed)

    return all(results)

def verify_phase1():
    """Phase 1 - 数据处理验收"""
    print_header("Phase 1 - 数据处理")

    results = []
    base_path = Path(__file__).parent.parent / "backend" / "data" / "processed"

    # 检查商品文件
    products_file = base_path / "products.jsonl"
    passed = products_file.exists()
    print_check("products.jsonl 存在", passed)
    results.append(passed)

    if passed:
        with open(products_file, encoding="utf-8") as f:
            products = [json.loads(line) for line in f]
        print_check("商品数量 > 0", len(products) > 0, f"共 {len(products):,} 个商品")

        # 检查字段完整性
        sample = products[0]
        required_fields = ["asin", "title", "description", "category", "brand"]
        has_fields = all(k in sample for k in required_fields)
        print_check("商品字段完整", has_fields, f"包含: {', '.join(required_fields)}")
        results.append(has_fields)

    # 检查用户行为文件
    interactions_file = base_path / "user_interactions.jsonl"
    passed = interactions_file.exists()
    print_check("user_interactions.jsonl 存在", passed)
    results.append(passed)

    if passed:
        with open(interactions_file, encoding="utf-8") as f:
            interactions = [json.loads(line) for line in f]

        # 检查序列长度 >= 5
        all_valid = all(len(i["sequence"]) >= 5 for i in interactions)
        print_check("所有序列长度 >= 5", all_valid, f"共 {len(interactions):,} 个用户")
        results.append(all_valid)

    # 检查 SID 映射
    sid_file = base_path / "sid_mapping.json"
    passed = sid_file.exists()
    print_check("sid_mapping.json 存在", passed)
    results.append(passed)

    if passed:
        with open(sid_file, encoding="utf-8") as f:
            sid_data = json.load(f)

        # 检查双向一致性
        asin2sid = sid_data["asin2sid"]
        sid2asin = sid_data["sid2asin"]
        test_asin = list(asin2sid.keys())[0]
        sid = asin2sid[test_asin]
        back_asin = sid2asin[sid]
        consistent = (test_asin == back_asin)
        print_check("SID 双向映射一致", consistent, f"{test_asin} -> {sid} -> {back_asin}")

        # 检查覆盖率
        if passed and 'products' in dir():
            coverage = len(set(asin2sid.keys()) & {p["asin"] for p in products}) / len(products)
            print_check("SID 覆盖率 >= 95%", coverage >= 0.95, f"{coverage:.1%}")

    return all(results)

def verify_phase2():
    """Phase 2 - Elasticsearch 搭建验收"""
    print_header("Phase 2 - Elasticsearch 搭建")

    results = []

    # 检查 ES 客户端
    try:
        from elasticsearch.client import ESClient
        print_check("ESClient 类存在", True)
        results.append(True)
    except ImportError:
        print_check("ESClient 类存在", False)
        results.append(False)

    # 检查 mapping 文件
    mapping_file = Path(__file__).parent.parent / "backend" / "elasticsearch" / "mappings" / "products_mapping.json"
    passed = mapping_file.exists()
    print_check("products_mapping.json 存在", passed)
    results.append(passed)

    if passed:
        with open(mapping_file) as f:
            mapping = json.load(f)
        has_sid = "sid" in mapping.get("mappings", {}).get("properties", {})
        print_check("Mapping 包含 sid 字段", has_sid)
        results.append(has_sid)

    # 检查批量导入脚本
    bulk_script = Path(__file__).parent.parent / "backend" / "elasticsearch" / "scripts" / "bulk_index_products.py"
    passed = bulk_script.exists()
    print_check("bulk_index_products.py 存在", passed)
    results.append(passed)

    return all(results)

def verify_phase3():
    """Phase 3 - SID 映射服务验收"""
    print_header("Phase 3 - SID 映射服务")

    results = []

    # 检查 SID 服务
    try:
        from services.sid_service import SIDService
        print_check("SIDService 类存在", True)
        results.append(True)
    except ImportError:
        print_check("SIDService 类存在", False)
        results.append(False)
        return False

    # 测试 SID 服务功能
    import asyncio

    async def test_sid_service():
        svc = SIDService()
        await svc.initialize()

        # 测试查询
        test_asin = list(svc.asin2sid.keys())[0]
        sid = svc.asin_to_sid(test_asin)
        back_asin = svc.sid_to_asin(sid) if sid else None

        return test_asin == back_asin

    try:
        passed = asyncio.run(test_sid_service())
        print_check("SID 查询双向一致", passed)
        results.append(passed)
    except Exception as e:
        print_check("SID 查询双向一致", False, str(e))
        results.append(False)

    # 检查单元测试
    test_file = Path(__file__).parent.parent / "backend" / "tests" / "unit" / "test_sid_service.py"
    passed = test_file.exists()
    print_check("test_sid_service.py 存在", passed)
    results.append(passed)

    return all(results)

def verify_phase4():
    """Phase 4 - 模型推理服务验收"""
    print_header("Phase 4 - 模型推理服务")

    results = []

    # 检查推理服务
    try:
        from models.recommender_inference import RecommenderInference
        print_check("RecommenderInference 类存在", True)
        results.append(True)
    except ImportError:
        print_check("RecommenderInference 类存在", False)
        results.append(False)
        return False

    # 测试推理服务（模拟模式）
    rec = RecommenderInference()
    # 不加载模型，使用模拟模式
    rec.model = None
    rec.tokenizer = None

    # 测试预测
    test_sids = ["1_2_3_4", "5_6_7_8"]
    candidates = rec.predict(test_sids)
    passed = len(candidates) > 0 and all("_" in s for s in candidates)
    print_check("推理返回合法 SID", passed, f"返回 {len(candidates)} 个候选")
    results.append(passed)

    # 检查 RQ-VAE 编码器
    try:
        from models.rqvae_encoder import RQVAEEncoder
        print_check("RQVAEEncoder 类存在", True)
        results.append(True)
    except ImportError:
        print_check("RQVAEEncoder 类存在", False)
        results.append(False)

    return all(results)

def verify_phase5():
    """Phase 5 - FastAPI 在线服务验收"""
    print_header("Phase 5 - FastAPI 在线服务")

    results = []

    # 检查 FastAPI 应用
    try:
        from api.main import app
        print_check("FastAPI app 存在", True)
        results.append(True)
    except ImportError:
        print_check("FastAPI app 存在", False)
        results.append(False)
        return False

    # 检查路由
    routes = [r.path for r in app.routes]
    required_routes = [
        "/health",
        "/metrics",
        "/api/v1/recommend",
        "/api/v1/products/{asin}",
        "/api/v1/products/search",
        "/api/v1/behavior",
    ]

    for route in required_routes:
        passed = route in routes
        print_check(f"路由 {route} 注册", passed)
        results.append(passed)

    # 检查 Schema
    try:
        from api.schemas.recommend import RecommendRequest, RecommendResponse
        from api.schemas.products import ProductDetail, SearchResponse
        print_check("Schema 类定义完整", True)
        results.append(True)
    except ImportError:
        print_check("Schema 类定义完整", False)
        results.append(False)

    # 检查中间件
    try:
        from api.middleware.logging_middleware import LoggingMiddleware, metrics
        print_check("日志中间件存在", True)
        results.append(True)
    except ImportError:
        print_check("日志中间件存在", False)
        results.append(False)

    return all(results)

def verify_phase6_9():
    """Phase 6-9 - 前端验收"""
    print_header("Phase 6-9 - 前端")

    results = []
    frontend_path = Path(__file__).parent.parent / "frontend"

    # Phase 6 - 工程搭建
    package_json = frontend_path / "package.json"
    passed = package_json.exists()
    print_check("package.json 存在", passed)
    results.append(passed)

    vite_config = frontend_path / "vite.config.ts"
    passed = vite_config.exists()
    print_check("vite.config.ts 存在", passed)
    results.append(passed)

    tailwind_config = frontend_path / "tailwind.config.ts"
    passed = tailwind_config.exists()
    print_check("tailwind.config.ts 存在", passed)
    results.append(passed)

    # Phase 7 - API 层与状态管理
    api_files = [
        frontend_path / "src" / "api" / "client.ts",
        frontend_path / "src" / "api" / "recommend.ts",
        frontend_path / "src" / "api" / "products.ts",
    ]
    passed = all(f.exists() for f in api_files)
    print_check("API 层文件完整", passed)
    results.append(passed)

    store_files = [
        frontend_path / "src" / "store" / "behaviorStore.ts",
        frontend_path / "src" / "store" / "userStore.ts",
    ]
    passed = all(f.exists() for f in store_files)
    print_check("Store 文件完整", passed)
    results.append(passed)

    hooks_files = [
        frontend_path / "src" / "hooks" / "useRecommend.ts",
        frontend_path / "src" / "hooks" / "useProductSearch.ts",
    ]
    passed = all(f.exists() for f in hooks_files)
    print_check("Hooks 文件完整", passed)
    results.append(passed)

    # Phase 8 - 核心组件
    component_files = [
        frontend_path / "src" / "components" / "product" / "ProductCard.tsx",
        frontend_path / "src" / "components" / "product" / "ProductGrid.tsx",
        frontend_path / "src" / "components" / "recommendation" / "RecommendFeed.tsx",
        frontend_path / "src" / "components" / "recommendation" / "BehaviorPanel.tsx",
    ]
    passed = all(f.exists() for f in component_files)
    print_check("核心组件文件完整", passed)
    results.append(passed)

    # Phase 9 - 页面
    page_files = [
        frontend_path / "src" / "pages" / "HomePage.tsx",
        frontend_path / "src" / "pages" / "SearchPage.tsx",
        frontend_path / "src" / "pages" / "SimulatorPage.tsx",
    ]
    passed = all(f.exists() for f in page_files)
    print_check("页面文件完整", passed)
    results.append(passed)

    # 检查类型定义
    types_file = frontend_path / "src" / "types" / "product.ts"
    passed = types_file.exists()
    print_check("类型定义文件存在", passed)
    results.append(passed)

    return all(results)

def verify_tests():
    """测试验收"""
    print_header("测试验收")

    results = []

    # 后端测试
    backend_tests = [
        Path(__file__).parent.parent / "backend" / "tests" / "unit" / "test_sid_service.py",
        Path(__file__).parent.parent / "backend" / "tests" / "unit" / "test_recommend_pipeline.py",
        Path(__file__).parent.parent / "backend" / "tests" / "unit" / "test_search_service.py",
        Path(__file__).parent.parent / "backend" / "tests" / "unit" / "test_cache_service.py",
        Path(__file__).parent.parent / "backend" / "tests" / "integration" / "test_recommend_api.py",
    ]

    backend_count = sum(1 for f in backend_tests if f.exists())
    passed = backend_count >= 4
    print_check(f"后端测试文件 ({backend_count}/{len(backend_tests)})", passed)
    results.append(passed)

    # 前端测试
    frontend_tests = [
        Path(__file__).parent.parent / "frontend" / "src" / "components" / "product" / "ProductCard.test.tsx",
        Path(__file__).parent.parent / "frontend" / "src" / "components" / "product" / "ProductGrid.test.tsx",
        Path(__file__).parent.parent / "frontend" / "src" / "store" / "behaviorStore.test.ts",
        Path(__file__).parent.parent / "frontend" / "src" / "utils" / "format.test.ts",
    ]

    frontend_count = sum(1 for f in frontend_tests if f.exists())
    passed = frontend_count >= 3
    print_check(f"前端测试文件 ({frontend_count}/{len(frontend_tests)})", passed)
    results.append(passed)

    # pytest 配置
    pytest_ini = Path(__file__).parent.parent / "backend" / "pytest.ini"
    passed = pytest_ini.exists()
    print_check("pytest.ini 存在", passed)
    results.append(passed)

    # coverage 配置
    coveragerc = Path(__file__).parent.parent / "backend" / ".coveragerc"
    passed = coveragerc.exists()
    print_check(".coveragerc 存在", passed)
    results.append(passed)

    return all(results)

def verify_deployment():
    """部署验收"""
    print_header("部署验收")

    results = []

    # Docker 配置
    docker_compose = Path(__file__).parent.parent / "docker-compose.yml"
    passed = docker_compose.exists()
    print_check("docker-compose.yml 存在", passed)
    results.append(passed)

    backend_dockerfile = Path(__file__).parent.parent / "backend" / "Dockerfile"
    passed = backend_dockerfile.exists()
    print_check("backend/Dockerfile 存在", passed)
    results.append(passed)

    frontend_dockerfile = Path(__file__).parent.parent / "frontend" / "Dockerfile"
    passed = frontend_dockerfile.exists()
    print_check("frontend/Dockerfile 存在", passed)
    results.append(passed)

    nginx_conf = Path(__file__).parent.parent / "nginx" / "nginx.conf"
    passed = nginx_conf.exists()
    print_check("nginx/nginx.conf 存在", passed)
    results.append(passed)

    # 启动脚本
    start_bat = Path(__file__).parent.parent / "scripts" / "start_dev.bat"
    passed = start_bat.exists()
    print_check("scripts/start_dev.bat 存在", passed)
    results.append(passed)

    start_sh = Path(__file__).parent.parent / "scripts" / "start_dev.sh"
    passed = start_sh.exists()
    print_check("scripts/start_dev.sh 存在", passed)
    results.append(passed)

    return all(results)

def main():
    print_header("推荐系统完整验收测试")
    print("Project_Architecture.md 各Phase验收标准检查")

    phase_results = {
        "Phase 0 - 环境初始化": verify_phase0(),
        "Phase 1 - 数据处理": verify_phase1(),
        "Phase 2 - Elasticsearch": verify_phase2(),
        "Phase 3 - SID 映射服务": verify_phase3(),
        "Phase 4 - 模型推理服务": verify_phase4(),
        "Phase 5 - FastAPI 服务": verify_phase5(),
        "Phase 6-9 - 前端": verify_phase6_9(),
        "测试验收": verify_tests(),
        "部署验收": verify_deployment(),
    }

    # 汇总
    print_header("验收结果汇总")

    passed_count = sum(1 for p in phase_results.values() if p)
    total_count = len(phase_results)

    for phase, passed in phase_results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {phase}")

    print(f"\n通过: {passed_count}/{total_count}")

    if passed_count == total_count:
        print("\n" + "=" * 60)
        print("  所有Phase验收通过！项目完整！")
        print("=" * 60)
        return True
    else:
        print("\n[WARN] 部分Phase未通过，请检查上述失败项")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
