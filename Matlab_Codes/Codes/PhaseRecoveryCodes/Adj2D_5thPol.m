function [mat_int] = Adj2D_5thPol(mat,x,y,xev,yev)

    Mask = x*0+1;
    TT=polyfit2D_1_5(mat,Mask,x,y,5);

    mat_int=PolyVal2D_1_5(TT,xev,yev,5);

end




function TT=polyfit2D_1_5(mat,Mask,x,y,N)
%TT=polyfit2D_1(mat,Mask,x,y,N);
%Function pour obtenir le polinome de N degree 2D selon les suivantes ordres
%
%xN xN-1y xN-2y2.....xyN-1 yN
%.......
%x4 x3y x2y2 xy3 y4
%x3 x2y xy2 y3
%x2 xy y2
%x y
%1
%La matrix es vecteurisée dans le sens verticalle. On utilise Mask pour valider les points
%Le vecteur de sortie TT donne les coefficients:
%m=length(TT);
%TT(m)=const
%TT(m-1)=y;  TT(m-2)=x;
%TT(m-3)=y2;  TT(m-4)=xy; TT(m-5)=x2;
%......

% width=size(mat,2);
% height=size(mat,1);
% if ischar(x) | ischar(y) | ischar(Mask) | ischar(mat) | ischar(N)
%     error('Datos de entrada no validos...');
%     return;
% end
% if (size(x,1)*size(x,2) == 1) | (size(y,1)*size(y,2) == 1)
%     error('dimension de x y y  no valida.');
%     return;
% end
% 
% if (size(N,1)*size(N,2) ~= 1 | N<=0)
%     error('dimension de N  no valida.');
%     return;
% end
% 
% if (size(mat)~=size(Mask))
%     error('dimension de matrices  no valida.');
%     return;
% end
% 
% if ( prod(size(x))== size(x,1) | prod(size(x))== size(x,2) ) & ( prod(size(y))== size(y,1) | prod(size(y))== size(y,2) )
%     if (length(x)~=width | length(y)~=height)
%         error('dimension de matrices  no valida.');
%         return;
%     end
%     [X,Y]=meshgrid(x,y);
%     x=[];y=[];
% elseif ( size(x)==size(y) & size(x)==size(mat) )
%     X=x;Y=y;
%     x=[];y=[];
% end
% 
% LM=reshape(Mask,[width*height 1]);
% indVal=find(LM==1);%clear LM;
% %clear Mask;
% LX=reshape(X,[width*height 1]);%X=[];
% X=LX(indVal);%clear LX;
% LY=reshape(Y,[width*height 1]);%Y=[];
% Y=LY(indVal);%clear LY;
% LI=reshape(mat,[width*height 1]);
X = x;
Y = y;
I= mat;%clear LI;clear mat;
% NDA=(N+1)*(N+2)/2;
% A=zeros(length(Y),NDA);
% cont=1;

% for n=N:-1:0
%     for l=n:-1:0
%         a=(X.^l).*(Y.^(n-l));
%         A(:,cont)=a;
%         cont=cont+1;
%     end
% end
ux = mean(X); sx = std(X);
uy = mean(Y); sy = std(Y);

X = (X-ux)/sx;
Y = (Y-uy)/sy;

X2 = X.*X; X3 = X2.*X;
Y2 = Y.*Y; Y3 = Y.*Y2;
A = [X2.*X3,X2.*X2.*Y,X3.*Y2,X2.*Y3,X.*Y2.*Y2,Y3.*Y2,X2.*X2,X3.*Y,X2.*Y2,X.*Y3,Y2.*Y2,X3,X2.*Y,X.*Y2,Y3,X2,X.*Y,Y2,X,Y,Y.*0+1];

% TT=inv(A'*A)*A'*I;

AA=A'*A;
b=A'*I;
TT=AA\b;



A = (TT(1)/sx^5);
B = (TT(2)/(sx^4*sy));
C = (TT(3)/(sx^3*sy^2)); % X3*Y2
D = (TT(4)/(sx^2*sy^3)); % X2Y3
E = (TT(5)/(sx*sy^4)); %XY4
F = (TT(6)/sy^5); %Y5
G = (TT(7)/sx^4 - (5*TT(1)*ux)/sx^5 - (TT(2)*uy)/(sx^4*sy)); % X4
H = (TT(8)/(sx^3*sy) - (4*TT(2)*ux)/(sx^4*sy) - (2*TT(3)*uy)/(sx^3*sy^2)); % X3Y
I = (TT(9)/(sx^2*sy^2) - (3*TT(3)*ux)/(sx^3*sy^2) - (3*TT(4)*uy)/(sx^2*sy^3)); %X2Y2
J = (TT(10)/(sx*sy^3) - (2*TT(4)*ux)/(sx^2*sy^3) - (4*TT(5)*uy)/(sx*sy^4)); % XY3
K = (TT(11)/sy^4 - (5*TT(6)*uy)/sy^5 - (TT(5)*ux)/(sx*sy^4)); %Y4
L = (TT(12)/sx^3 - (4*TT(7)*ux)/sx^4 + (10*TT(1)*ux^2)/sx^5 + (TT(3)*uy^2)/(sx^3*sy^2) - (TT(8)*uy)/(sx^3*sy) + (4*TT(2)*ux*uy)/(sx^4*sy)); % X3
M = (TT(13)/(sx^2*sy) + (6*TT(2)*ux^2)/(sx^4*sy) + (3*TT(4)*uy^2)/(sx^2*sy^3) - (3*TT(8)*ux)/(sx^3*sy) - (2*TT(9)*uy)/(sx^2*sy^2) + (6*TT(3)*ux*uy)/(sx^3*sy^2));%X2Y
N = (TT(14)/(sx*sy^2) + (3*TT(3)*ux^2)/(sx^3*sy^2) + (6*TT(5)*uy^2)/(sx*sy^4) - (2*TT(9)*ux)/(sx^2*sy^2) - (3*TT(10)*uy)/(sx*sy^3) + (6*TT(4)*ux*uy)/(sx^2*sy^3));% XY2
O = (TT(15)/sy^3 - (4*TT(11)*uy)/sy^4 + (10*TT(6)*uy^2)/sy^5 + (TT(4)*ux^2)/(sx^2*sy^3) - (TT(10)*ux)/(sx*sy^3) + (4*TT(5)*ux*uy)/(sx*sy^4)); % Y3
P = (TT(16)/sx^2 - (3*TT(12)*ux)/sx^3 - (10*TT(1)*ux^3)/sx^5 + (6*TT(7)*ux^2)/sx^4 - (TT(4)*uy^3)/(sx^2*sy^3) + (TT(9)*uy^2)/(sx^2*sy^2) - (TT(13)*uy)/(sx^2*sy) + (3*TT(8)*ux*uy)/(sx^3*sy) - (6*TT(2)*ux^2*uy)/(sx^4*sy) - (3*TT(3)*ux*uy^2)/(sx^3*sy^2)); %X2
Q = (TT(17)/(sx*sy) - (4*TT(2)*ux^3)/(sx^4*sy) - (4*TT(5)*uy^3)/(sx*sy^4) + (3*TT(8)*ux^2)/(sx^3*sy) + (3*TT(10)*uy^2)/(sx*sy^3) - (2*TT(13)*ux)/(sx^2*sy) - (2*TT(14)*uy)/(sx*sy^2) + (4*TT(9)*ux*uy)/(sx^2*sy^2) - (6*TT(3)*ux^2*uy)/(sx^3*sy^2) - (6*TT(4)*ux*uy^2)/(sx^2*sy^3)); %XY
R = (TT(18)/sy^2 - (3*TT(15)*uy)/sy^3 - (10*TT(6)*uy^3)/sy^5 + (6*TT(11)*uy^2)/sy^4 - (TT(3)*ux^3)/(sx^3*sy^2) + (TT(9)*ux^2)/(sx^2*sy^2) - (TT(14)*ux)/(sx*sy^2) + (3*TT(10)*ux*uy)/(sx*sy^3) - (3*TT(4)*ux^2*uy)/(sx^2*sy^3) - (6*TT(5)*ux*uy^2)/(sx*sy^4)); %Y2
S = (TT(19)/sx - (2*TT(16)*ux)/sx^2 + (5*TT(1)*ux^4)/sx^5 - (4*TT(7)*ux^3)/sx^4 + (3*TT(12)*ux^2)/sx^3 + (TT(5)*uy^4)/(sx*sy^4) - (TT(10)*uy^3)/(sx*sy^3) + (TT(14)*uy^2)/(sx*sy^2) - (TT(17)*uy)/(sx*sy) + (3*TT(3)*ux^2*uy^2)/(sx^3*sy^2) + (2*TT(13)*ux*uy)/(sx^2*sy) + (4*TT(2)*ux^3*uy)/(sx^4*sy) + (2*TT(4)*ux*uy^3)/(sx^2*sy^3) - (3*TT(8)*ux^2*uy)/(sx^3*sy) - (2*TT(9)*ux*uy^2)/(sx^2*sy^2)); %X
T = (TT(20)/sy - (2*TT(18)*uy)/sy^2 + (5*TT(6)*uy^4)/sy^5 - (4*TT(11)*uy^3)/sy^4 + (3*TT(15)*uy^2)/sy^3 + (TT(2)*ux^4)/(sx^4*sy) - (TT(8)*ux^3)/(sx^3*sy) + (TT(13)*ux^2)/(sx^2*sy) - (TT(17)*ux)/(sx*sy) + (3*TT(4)*ux^2*uy^2)/(sx^2*sy^3) + (2*TT(14)*ux*uy)/(sx*sy^2) + (2*TT(3)*ux^3*uy)/(sx^3*sy^2) + (4*TT(5)*ux*uy^3)/(sx*sy^4) - (2*TT(9)*ux^2*uy)/(sx^2*sy^2) - (3*TT(10)*ux*uy^2)/(sx*sy^3)); %Y
U = TT(21) - (TT(19)*ux)/sx - (TT(20)*uy)/sy - (TT(1)*ux^5)/sx^5 - (TT(6)*uy^5)/sy^5 + (TT(7)*ux^4)/sx^4 + (TT(11)*uy^4)/sy^4 - (TT(12)*ux^3)/sx^3 - (TT(15)*uy^3)/sy^3 + (TT(16)*ux^2)/sx^2 + (TT(18)*uy^2)/sy^2 - (TT(3)*ux^3*uy^2)/(sx^3*sy^2) - (TT(4)*ux^2*uy^3)/(sx^2*sy^3) + (TT(9)*ux^2*uy^2)/(sx^2*sy^2) + (TT(17)*ux*uy)/(sx*sy) - (TT(2)*ux^4*uy)/(sx^4*sy) - (TT(5)*ux*uy^4)/(sx*sy^4) + (TT(8)*ux^3*uy)/(sx^3*sy) + (TT(10)*ux*uy^3)/(sx*sy^3) - (TT(13)*ux^2*uy)/(sx^2*sy) - (TT(14)*ux*uy^2)/(sx*sy^2);

TT = [A;B;C;D;E;F;G;H;I;J;K;L;M;N;O;P;Q;R;S;T;U];



clear A;clear X;clear Y;clear I;clear indVal;
end




function matA=PolyVal2D_1_5(TT,x,y,N)
% x,y son vectores que definen las coordenadas de los puntos donde se va a evaluar el polinomio.
%Esta funcion asume que se desea evaluar la zona definida por x y y para
%generar una matriz de valores. Generalmente se usa asuminedo x=1:Num Colu
%y=1:Num Filas.
%Function pour evaluer le polynome TT de degree N avec x,y
%xN xN-1y xN-2y2.....xyN-1 yN
%.......
%x4 x3y x2y2 xy3 y4
%x3 x2y xy2 y3
%x2 xy y2
%x y
%1

NDA=(N+1)*(N+2)/2;

iptcheckinput(TT, {'double','single'}, {'real','vector','nonsparse', 'nonempty',...
    'finite'},mfilename, 'TT', 1);
iptcheckinput(x, {'double','single'}, {'real','vector','nonsparse', 'nonempty',...
    'finite'},mfilename, 'x', 2);
iptcheckinput(y, {'double','single'}, {'real','vector','nonsparse', 'nonempty',...
    'finite'},mfilename, 'y', 3);
iptcheckinput(N, {'double','single'}, {'real', 'scalar', 'integer', 'positive',...
    'finite'},mfilename, 'N', 4);


if (length(TT)~=NDA)
    ui=errordlg('Dimension de TT no valida','PolyVal2D_1');
    waitfor(ui);
    return;
end
[X,Y]=meshgrid(x,y);
if N>=7 & length(X(:))>=500000
    X=[];Y=[];
    matA=zeros(length(y),length(x));
    disp('    polyval2D_1.m:evaluacion camino largo');
    for ix=1:length(x)
        valx=x(ix);
        LY=y;
        LX=valx*ones(size(LY));
        A=zeros(length(LY),NDA);
        cont=1;
        for n=N:-1:0
            for l=n:-1:0
                a=(LX.^l).*(LY.^(n-l));
                A(:,cont)=a;
                cont=cont+1;
            end
        end
        LA=A*TT;
        matA(:,ix)=LA;
    end
else

    [height,width]=size(X);
    X=reshape(X,[width*height 1]);
    Y=reshape(Y,[width*height 1]);

    %     A=zeros(length(Y),NDA);
    %     cont=1;

    X2 = X.*X; X3 = X2.*X;
    Y2 = Y.*Y; Y3 = Y.*Y2;
    A = [X2.*X3,X2.*X2.*Y,X3.*Y2,X2.*Y3,X.*Y2.*Y2,Y3.*Y2,X2.*X2,X3.*Y,X2.*Y2,X.*Y3,Y2.*Y2,X3,X2.*Y,X.*Y2,Y3,X2,X.*Y,Y2,X,Y,Y.*0+1];


    matA=A*TT;
    matA=reshape(matA,[height,width]);
end
end