// frontend/src/pages/AuthTestPage.tsx
import React from "react";
import { useAuthSetup } from "../hooks/useAuthSetup";
import { AuthGuard } from "../components/AuthGuard";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "../utils/apiClient";

const AuthTestPage: React.FC = () => {
  const { isAuthenticated, isLoading, user } = useAuth0();
  const { isReady, userId, error: authError } = useAuthSetup();
  const api = useApiClient();

  return (
    <AuthGuard>
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h1 className="text-2xl font-bold mb-6">🔐 Authentication Test Page</h1>

        <div className="space-y-4">
          {/* Auth0 Status */}
          <div className="border rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-2">Auth0 Status</h2>
            <div className="space-y-2">
              <p><strong>Loading:</strong> {isLoading ? "Yes" : "No"}</p>
              <p><strong>Authenticated:</strong> {isAuthenticated ? "Yes" : "No"}</p>
              <p><strong>User Email:</strong> {user?.email || "Not available"}</p>
              <p><strong>User Name:</strong> {user?.name || "Not available"}</p>
            </div>
          </div>

          {/* Centralized Auth Setup Status */}
          <div className="border rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-2">Centralized Auth Setup</h2>
            <div className="space-y-2">
              <p><strong>Ready:</strong> {isReady ? "✅ Yes" : "⏳ No"}</p>
              <p><strong>User ID:</strong> {userId || "Not set"}</p>
              <p><strong>Error:</strong> {authError || "None"}</p>
            </div>
          </div>

          {/* Test API Call */}
          <div className="border rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-2">Test API Call</h2>
            <p className="text-sm text-gray-600 mb-2">
              This will test if the centralized authentication allows API calls to work.
            </p>
            <button
              onClick={async () => {
                try {
                  const response = await api.get("/user");
                  alert(`✅ API call successful!\nResponse: ${JSON.stringify(response.data, null, 2)}`);
                } catch (error: any) {
                  alert(`❌ API call failed!\nError: ${error.message}`);
                }
              }}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
              disabled={!isReady}
            >
              Test API Call
            </button>
            <p className="text-xs text-gray-500 mt-2">
              {!isReady ? "Wait for authentication to be ready..." : "Ready to test!"}
            </p>
          </div>

          {/* Status Summary */}
          <div className={`border rounded-lg p-4 ${authError ? 'border-red-200 bg-red-50' : isReady ? 'border-green-200 bg-green-50' : 'border-yellow-200 bg-yellow-50'}`}>
            <h2 className="text-lg font-semibold mb-2">Status Summary</h2>
            {authError ? (
              <p className="text-red-600">❌ Authentication Error: {authError}</p>
            ) : isReady ? (
              <p className="text-green-600">✅ Authentication Ready - All systems working!</p>
            ) : (
              <p className="text-yellow-600">⏳ Setting up authentication...</p>
            )}
          </div>
        </div>
      </div>
    </div>
    </AuthGuard>
  );
};

export default AuthTestPage;
