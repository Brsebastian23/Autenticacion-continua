package com.autentication.service.impl;

import com.autentication.domain.User;
import com.autentication.dto.AuthResponse;
import com.autentication.dto.LoginRequest;
import com.autentication.dto.RegisterRequest;
import com.autentication.dto.UserResponse;
import com.autentication.exception.BadRequestException;
import com.autentication.exception.DuplicateResourceException;
import com.autentication.exception.ResourceNotFoundException;
import com.autentication.repository.UserRepository;
import com.autentication.security.JwtService;
import com.autentication.service.AuthService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Slf4j
public class AuthServiceImpl implements AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuthenticationManager authenticationManager;

    @Override
    @Transactional
    public UserResponse register(RegisterRequest request) {
        if (userRepository.existsByUsername(request.username())) {
            throw new DuplicateResourceException("El username ya está registrado.");
        }

        // Nota (modo demo): varios usuarios pueden elegir el mismo modelo del
        // dataset (p. ej. "s002") para probar cómo los evalúa. Los modelos
        // propios de cada usuario ("user-<username>") siguen siendo únicos
        // porque derivan del username (que ya es único).
        User user = new User(
                request.username(),
                passwordEncoder.encode(request.password()),
                request.keystrokeModelId());
        User saved = userRepository.save(user);
        log.info("Usuario registrado: {} (modelo={})", saved.getUsername(), saved.getKeystrokeModelId());
        return UserResponse.from(saved);
    }

    @Override
    public AuthResponse login(LoginRequest request) {
        try {
            authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(request.username(), request.password()));
        } catch (BadCredentialsException ex) {
            throw new BadRequestException("Credenciales inválidas.");
        }

        User user = userRepository.findByUsername(request.username())
                .orElseThrow(() -> new ResourceNotFoundException("Usuario no encontrado."));

        String token = jwtService.generateToken(user.getUsername(), user.getKeystrokeModelId());
        // Devolver el modelo activo (propio si ya entrenó; si no, el del dataset).
        return new AuthResponse(token, user.getUsername(), user.activeModelId());
    }

    @Override
    public UserResponse getByUsername(String username) {
        User user = userRepository.findByUsername(username)
                .orElseThrow(() -> new ResourceNotFoundException("Usuario no encontrado: " + username));
        return UserResponse.from(user);
    }
}
