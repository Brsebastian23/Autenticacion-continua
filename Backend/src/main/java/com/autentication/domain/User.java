package com.autentication.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

/**
 * Entidad de dominio que representa a un usuario del sistema.
 *
 * <p>El campo {@code keystrokeModelId} es el identificador que el modelo Python
 * (IsolationForest) espera como {@code user_id} (p. ej. "s002"). Esto desacopla
 * la identidad del usuario en el backend Java del identificador usado por el
 * modelo, permitiendo cambiar/entrenar modelos sin tocar la tabla de usuarios.</p>
 */
@Entity
@Table(name = "users",
        uniqueConstraints = {
                @UniqueConstraint(columnNames = "username")
        })
@Getter
@Setter
@NoArgsConstructor
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 64)
    private String username;

    /** Hash BCrypt de la contraseña; nunca la contraseña en claro. */
    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    /**
     * Modelo del dataset (p. ej. "s002") elegido al registrarse.
     * SOLO LECTURA: se usa para probar mientras el usuario no ha entrenado.
     * NUNCA se sobrescribe al entrenar (Opción 2).
     */
    @Column(name = "keystroke_model_id", nullable = false, length = 64)
    private String keystrokeModelId;

    /**
     * Modelo propio del usuario ({@code user-<username>}), generado al entrenar.
     * Mientras no lo haya entrenado, es {@code null}. Una vez entrenado, la
     * verificación usa este modelo en lugar del del dataset.
     */
    @Column(name = "trained_model_id", length = 128)
    private String trainedModelId;

    /** Indica si el usuario ya entrenó su modelo propio. */
    @Transient
    public boolean hasTrainedModel() {
        return trainedModelId != null && !trainedModelId.isBlank();
    }

    /**
     * Modelo que debe usarse para verificar: el propio si ya entrenó,
     * si no, el del dataset elegido en el registro.
     */
    @Transient
    public String activeModelId() {
        return hasTrainedModel() ? trainedModelId : keystrokeModelId;
    }

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void onCreate() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
    }

    public User(String username, String passwordHash, String keystrokeModelId) {
        this.username = username;
        this.passwordHash = passwordHash;
        this.keystrokeModelId = keystrokeModelId;
    }
}
