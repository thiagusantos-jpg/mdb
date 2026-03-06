import { useNavigate } from 'react-router-dom';
import { LoginForm } from '../components/Auth/LoginForm.jsx';

export default function LoginPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary-700">DuBairro</h1>
          <p className="text-gray-500 mt-1">Gestão de Dados e Sincronização</p>
        </div>
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-800 mb-6">Entrar</h2>
          <LoginForm onSuccess={() => navigate('/dashboard')} />
        </div>
        <p className="text-center text-xs text-gray-400 mt-4">
          admin@dubairro.com / admin123
        </p>
      </div>
    </div>
  );
}
