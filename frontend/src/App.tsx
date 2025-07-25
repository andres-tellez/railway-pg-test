import { Routes, Route } from "react-router-dom";
import OnboardScreen from "./OnboardScreen";
import AskGptMvpUI from "./AskGptMvpUI";
import PostOAuthSuccess from "./PostOAuthSuccess";
import LoginPage from "./components/LoginPage";
import React from "react"; // ✅ required for JSX if not globally imported

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100 p-4">
        <Routes>
          <Route path="/" element={<OnboardScreen />} />
      {/* <Route path="/auth/login" element={<LoginPage />} /> */}
          <Route path="/auth/callback" element={<PostOAuthSuccess />} /> 
      {/* <Route path="/ask" element={<AskGptMvpUI />} /> */}
      {/* <Route path="/post-oauth" element={<PostOAuthSuccess />} /> */}
      </Routes>
    </div>
  );
};

export default App;
