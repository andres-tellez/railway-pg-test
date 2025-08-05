import { Routes, Route } from "react-router-dom";
import React from "react";
import OnboardingForm from "./pages/OnboardingForm";
import PostOAuthSuccess from "./pages/PostOAuthSuccess";
import LoginPage from "./pages/LoginPage";
import AskGptMvpUI from "./pages/AskGptMvpUI";
import Dashboard from "./pages/Dashboard";

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <Routes>
        <Route path="/" element={<OnboardingForm />} />
        <Route path="/onboarding" element={<OnboardingForm />} />
        <Route path="/post-oauth" element={<PostOAuthSuccess />} />
        <Route path="/auth/login" element={<LoginPage />} />
        <Route path="/ask" element={<AskGptMvpUI />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </div>
  );
};

export default App;
