import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

// 请求拦截：统一注入用户 ID
apiClient.interceptors.request.use((config) => {
  const userId = localStorage.getItem("rec_user_id") ?? "demo_user";
  config.headers["X-User-Id"] = userId;
  return config;
});

// 响应拦截：统一错误处理
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    const msg = error.response?.data?.detail ?? "请求失败，请稍后重试";
    console.error("[API Error]", msg);
    return Promise.reject(new Error(msg));
  }
);

export default apiClient;
