package com.autentication.service;

import com.autentication.dto.AuthResponse;
import com.autentication.dto.LoginRequest;
import com.autentication.dto.RegisterRequest;
import com.autentication.dto.UserResponse;

/**
 * Contrato de servicios de autenticación y gestión de usuarios.
 * Las capas superiores (controladores) dependen de esta abstracción.
 */
public interface AuthService {

    UserResponse register(RegisterRequest request);

    AuthResponse login(LoginRequest request);

    UserResponse getByUsername(String username);
}
