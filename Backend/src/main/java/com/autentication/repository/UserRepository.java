package com.autentication.repository;

import com.autentication.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/**
 * Repositorio de persistencia de usuarios (capa de acceso a datos).
 * Es una abstracción (interfaz) — las capas superiores dependen de esta,
 * no de una implementación concreta (Principio de Inversión de Dependencias).
 */
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUsername(String username);

    boolean existsByUsername(String username);
}
