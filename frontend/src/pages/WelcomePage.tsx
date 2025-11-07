/**
 * @file WelcomePage.tsx
 * @component WelcomePage
 * @description Public welcome page for new users explaining the app
 * 
 * @features:
 * - App introduction and value proposition
 * - Call-to-action to get started
 * - Clean, welcoming design
 * - No authentication required
 */

import React from 'react';
import { Link } from 'react-router-dom';

const WelcomePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="pt-16 pb-20 text-center">
          <div className="flex justify-center mb-8">
            <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center">
              <span className="text-white font-bold text-2xl">SC</span>
            </div>
          </div>
          
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            Welcome to SmartCoach
          </h1>
          
          <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
            Your AI-powered running coach that creates personalized training plans 
            based on your Strava data and race goals.
          </p>
          
          <Link
            to="/login"
            className="inline-flex items-center px-8 py-4 border border-transparent text-lg font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-lg hover:shadow-xl"
          >
            Get Started
            <svg className="ml-2 w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        </div>

        {/* Features */}
        <div className="py-16">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">📊</span>
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                Strava Integration
              </h3>
              <p className="text-gray-600">
                Connect your Strava account to analyze your training history and create personalized plans.
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🤖</span>
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                AI Coaching
              </h3>
              <p className="text-gray-600">
                Get personalized advice and training recommendations from our AI coach.
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🎯</span>
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                Goal-Oriented Plans
              </h3>
              <p className="text-gray-600">
                Training plans tailored to your specific race goals and fitness level.
              </p>
            </div>
          </div>
        </div>

        {/* How it Works */}
        <div className="py-16 bg-white rounded-2xl shadow-lg mb-16">
          <div className="px-8">
            <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
              How It Works
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">
                  1
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  Connect Strava
                </h3>
                <p className="text-gray-600">
                  Link your Strava account to import your running history and activity data.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">
                  2
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  Set Your Goals
                </h3>
                <p className="text-gray-600">
                  Tell us about your race goals, training preferences, and fitness level.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">
                  3
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  Get Your Plan
                </h3>
                <p className="text-gray-600">
                  Receive a personalized training plan designed just for you.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center pb-16">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            Ready to Start Training Smarter?
          </h2>
          <p className="text-lg text-gray-600 mb-8">
            Join runners who are already using SmartCoach to reach their goals.
          </p>
          <Link
            to="/login"
            className="inline-flex items-center px-8 py-4 border border-transparent text-lg font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-lg hover:shadow-xl"
          >
            Start Your Journey
            <svg className="ml-2 w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default WelcomePage;
