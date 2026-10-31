% Entradas necesarias:
% I1, I2        - imágenes izquierda y derecha (grises o RGB)
% stereoParams  - objeto stereoParameters (calibrado)

% 1) Rectificar imágenes y obtener la matriz de reproyección Q

K1 = [1.02569330e+03 0.00000000e+00 6.66600994e+02; 0.00000000e+00 1.02721646e+03 3.25581862e+02; 0.00000000e+00 0.00000000e+00 1.00000000e+00]; 
dist1 = [-4.92199558e-01 3.39824260e-01 2.00439147e-03 2.23858245e-04 -1.84231702e-01];

K2 = [1.02751364e+03 0.00000000e+00 5.87607704e+02; 0.00000000e+00 1.02865433e+03 3.44608926e+02; 0.00000000e+00 0.00000000e+00 1.00000000e+00] ;
dist2 = [-5.07097404e-01 4.01292608e-01 1.12344540e-03 -4.13860328e-04 -2.70701400e-01];


R= [ 0.99998698 -0.00407376 0.0030718; 0.00403283 0.99990456 0.01321386; -0.00312534 -0.0132013 0.99990797];
T = [96.31861921 0.34955956 -0.48499002];

dire = 'C:\Users\ravargas\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\UTB\ARTICULOS\Articulo - STSIVA - YOLO ASISTENTE VISION\';



I1 = imread([dire 'rect_left.png']);
I2 = imread([dire 'rect_right.png']);


% Convertir a escala de grises si es necesario
if size(I1,3) == 3, gray1 = rgb2gray(I1); else gray1 = I1; end
if size(I2,3) == 3, gray2 = rgb2gray(I2); else gray2 = I2; end

% Detectar keypoints SIFT
points1 = detectSIFTFeatures(gray1);
points2 = detectSIFTFeatures(gray2);

% Mostrar detecciones (opcional)
figure('Name','SIFT keypoints');
subplot(1,2,1); imshow(I1); hold on; plot(selectStrongest(points1,100)); title('Imagen 1');
subplot(1,2,2); imshow(I2); hold on; plot(selectStrongest(points2,100)); title('Imagen 2');

% Extraer descriptores (SIFT devuelve vectores de 128)
[features1, validPts1] = extractFeatures(gray1, points1, Method="SIFT");
[features2, validPts2] = extractFeatures(gray2, points2, Method="SIFT");

% Emparejar descriptores
% Usamos 'MaxRatio' para ratio test y 'Unique' para correspondencias únicas
indexPairs = matchFeatures(features1, features2, MatchThreshold=100, MaxRatio=0.7, Unique=true);

matchedPts1 = validPts1(indexPairs(:,1));
matchedPts2 = validPts2(indexPairs(:,2));

% Visualizar matches iniciales
figure('Name','Matches iniciales');
showMatchedFeatures(I1, I2, matchedPts1, matchedPts2, 'montage');
title(sprintf('Matches iniciales: %d', size(indexPairs,1)));

% Filtrado con RANSAC: estimar transformación geométrica (afin o projectiva)
% Esto elimina outliers en las correspondencias.
if size(indexPairs,1) >= 3
    try
        [tform, inlierIdx] = estimateGeometricTransform2D(matchedPts2, matchedPts1, ...
            "affine", MaxDistance=4); % ajustar MaxDistance según escalas/ruido
    catch
        % Si falla (pocos inliers), no filtrar
        inlierIdx = true(size(indexPairs,1),1);
    end
else
    inlierIdx = true(size(indexPairs,1),1);
end

inlierMatched1 = matchedPts1(inlierIdx);
inlierMatched2 = matchedPts2(inlierIdx);

% Visualizar matches filtrados
figure('Name','Matches filtrados (RANSAC)');
showMatchedFeatures(I1, I2, inlierMatched1, inlierMatched2, 'montage');
title(sprintf('Matches filtrados (inliers): %d', sum(inlierIdx)));

% Resultados: puntos emparejados finales y matriz de índices
finalIndexPairs = indexPairs(inlierIdx, :);

% Opcional: mostrar coordenadas
matchedLocations1 = inlierMatched1.Location;
matchedLocations2 = inlierMatched2.Location;

% Guardar resultados en un .mat (opcional)
% save('sift_matches.mat','finalIndexPairs','matchedLocations1','matchedLocations2','tform');

% Mensaje resumen
fprintf('Matches iniciales: %d\nMatches después de RANSAC: %d\n', size(indexPairs,1), sum(inlierIdx));
%%

pts1 = matchedLocations1;
pts2 = matchedLocations2;


% -------------------------
% 2) Crear cameraParameters para undistortPoints
% Ajustar según longitud de dist (2,4 o 5 elementos)
% cameraParameters espera IntrinsicMatrix = K' (transpuesta)
aa = 0;
camParams1 = cameraParameters('IntrinsicMatrix', K1', ...
    'RadialDistortion', aa*dist1(1:min(2,end)), ...
    'TangentialDistortion', aa*(numel(dist1)>=4)*dist1(3:4));
camParams2 = cameraParameters('IntrinsicMatrix', K2', ...
    'RadialDistortion', aa*dist2(1:min(2,end)), ...
    'TangentialDistortion', aa*(numel(dist2)>=4)*dist2(3:4));



% -------------------------
% 3) Undistort de las coordenadas de puntos (obligatorio para triangulate)
undistortedPts1 = pts1;
undistortedPts2 = pts2;

% -------------------------
% 4) Construir matrices de proyección (3x4)
% Cámara 1 en el sistema de mundo: P1 = K1 * [I | 0]
P1 = K1 * [eye(3), zeros(3,1)];

% Cámara 2 respecto al sistema de la cámara 1: P2 = K2 * [R | t]
% Nota: si t es la traslación de cam1->cam2, usa t; si es de cam2->cam1, ajusta signo.
P2 = K2 * [R, t(:)];

% -------------------------
% 5) Triangulación
% triangulate acepta puntos en coordenadas de imagen undistortadas y P1,P2
[worldPoints, reprojErrors, validIndex] = triangulate(undistortedPts1, undistortedPts2, P1, P2);

% worldPoints es Nx3 en las mismas unidades que t (p. ej. mm o m).
% validIndex indica puntos delante de ambas cámaras; reprojErrors es el error de reproyección.

% -------------------------
% 6) Filtrado y visualización simple
validWorldPts = worldPoints(validIndex, :);
fprintf('Total correspondencias: %d\nPuntos válidos tras triangulación: %d\n', size(pts1,1), sum(validIndex));

% Opcional: visualizar puntos 3-D
figure;
pcshow(validWorldPts, 'MarkerSize', 50);
xlabel('X'); ylabel('Y'); zlabel('Z'); title('Puntos 3-D triangulados');

% -------------------------
% Resultado devuelto en workspace:
% worldPoints, reprojErrors, validIndex, validWorldPts



%%


% 2) Convertir a gris si es necesario
if size(J1,3) == 3
    J1g = rgb2gray(J1);
else
    J1g = J1;
end
if size(J2,3) == 3
    J2g = rgb2gray(J2);
else
    J2g = J2;
end

% 3) Calcular mapa de disparidad (ajustar parámetros según la escena)
dispRange = [0 128]; % rango de disparidad (ejemplo)
disparityMap = disparitySGM(J1g, J2g, DisparityRange=dispRange, ...
    NumDisparities=128, BlockSize=5);

% 4) Reproyectar a coordenadas 3-D (X, Y, Z)
points3D = reconstructScene(disparityMap, Q);  % devuelve matriz HxWx3 (en las mismas unidades que Q)

% 5) Convertir a metros si es necesario
% - Si stereoParams intrínsecos/traslación están en milímetros, dividir por 1000:
% points3D = points3D ./ 1000;

% 6) Crear nube de puntos y filtrar valores inválidos (disparidad <= 0)
X = points3D(:,:,1);
Y = points3D(:,:,2);
Z = points3D(:,:,3);
mask = disparityMap > 0 & isfinite(Z) & Z > 0;

xyz = [X(mask), Y(mask), Z(mask)];

% Obtener colores desde la imagen rectificada izquierda
colors = reshape(J1, [], size(J1,3));
colors = colors(mask(:), :);

ptCloud = pointCloud(xyz, Color=colors);

% 7) Visualizar
figure; pcshow(ptCloud, VerticalAxis='Y', VerticalAxisDir='Down');
xlabel('X'); ylabel('Y'); zlabel('Z');
title('Nube de puntos reconstruida por triangulación estéreo');
